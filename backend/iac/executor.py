import json
import re
import shutil
import subprocess
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .cmdb_sync import mark_stack_resources_offline, sync_stack_to_cmdb
from .models import TerraformExecution
from .terraform import build_render_payload, render_terraform_project


def run_terraform_action(stack, action, *, secrets, operator):
    payload = build_render_payload(
        name=stack.name,
        description=stack.description,
        cloud_provider=stack.cloud_provider,
        region=stack.region,
        zone=stack.zone,
        config=stack.config,
        secrets=secrets or {},
    )
    rendered = render_terraform_project(payload)
    stack.summary = rendered['summary']
    stack.generated_files = rendered['files']
    if operator:
        stack.updated_by = operator
    stack.save(update_fields=['summary', 'generated_files', 'updated_by'])

    execution = TerraformExecution.objects.create(
        stack=stack,
        action=action,
        status=TerraformExecution.STATUS_RUNNING,
        created_by=operator or '',
        started_at=timezone.now(),
    )

    terraform_bin = shutil.which('terraform')
    if not terraform_bin:
        return _finish_execution(
            stack,
            execution,
            status=TerraformExecution.STATUS_FAILED,
            return_code=-1,
            stderr='服务器未安装 terraform，可先部署 Terraform 二进制后再执行 init/plan/apply/destroy。',
        )

    commands = _build_commands(terraform_bin, action)
    execution.command = _build_command_display(commands)
    execution.save(update_fields=['command'])

    try:
        workspace = _prepare_workspace(stack, rendered['files'])
    except OSError as exc:
        return _finish_execution(
            stack,
            execution,
            status=TerraformExecution.STATUS_FAILED,
            return_code=-1,
            stderr=f'准备 Terraform 工作目录失败: {exc}',
        )

    stdout_parts = []
    stderr_parts = []
    return_code = 0

    for command in commands:
        try:
            result = subprocess.run(
                command,
                cwd=workspace,
                capture_output=True,
                text=True,
                encoding='utf-8',
                errors='ignore',
                timeout=900,
            )
        except subprocess.TimeoutExpired:
            return _finish_execution(
                stack,
                execution,
                status=TerraformExecution.STATUS_FAILED,
                return_code=-1,
                stdout='\n\n'.join(part for part in stdout_parts if part).strip(),
                stderr=f'{_format_command(command)} 执行超时，请检查云厂商接口连通性或缩小执行范围。',
                workspace=workspace,
            )
        except OSError as exc:
            return _finish_execution(
                stack,
                execution,
                status=TerraformExecution.STATUS_FAILED,
                return_code=-1,
                stdout='\n\n'.join(part for part in stdout_parts if part).strip(),
                stderr=f'{_format_command(command)} 执行失败: {exc}',
                workspace=workspace,
            )

        stdout_parts.append(f'$ {_format_command(command)}\n{result.stdout or ""}'.strip())
        if result.stderr:
            stderr_parts.append(f'$ {_format_command(command)}\n{result.stderr}'.strip())
        return_code = result.returncode
        if result.returncode != 0:
            break

    outputs = {}
    cmdb_summary = {}
    cmdb_synced = False
    status_value = TerraformExecution.STATUS_SUCCESS if return_code == 0 else TerraformExecution.STATUS_FAILED

    if return_code == 0 and action == TerraformExecution.ACTION_APPLY:
        outputs = _load_outputs(terraform_bin, workspace)
        cmdb_summary, cmdb_synced = _safe_sync_apply(stack, operator)
    elif return_code == 0 and action == TerraformExecution.ACTION_DESTROY:
        cmdb_summary, cmdb_synced = _safe_mark_destroyed(stack)
    elif return_code == 0 and action == TerraformExecution.ACTION_PLAN:
        cmdb_summary = {'detail': 'plan 成功，尚未回写 CMDB。'}
    elif return_code == 0 and action == TerraformExecution.ACTION_INIT:
        cmdb_summary = {'detail': 'init 成功，工作目录已准备完成。'}

    return _finish_execution(
        stack,
        execution,
        status=status_value,
        return_code=return_code,
        stdout='\n\n'.join(part for part in stdout_parts if part).strip(),
        stderr='\n\n'.join(part for part in stderr_parts if part).strip(),
        outputs=outputs,
        cmdb_summary=cmdb_summary,
        workspace=workspace,
        cmdb_synced=cmdb_synced,
    )


def _prepare_workspace(stack, files):
    workspace = Path(settings.BASE_DIR) / 'run' / 'iac' / f'stack-{stack.id}-{_slugify(stack.name)}'
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    for filename, content in files.items():
        if filename == 'README.md':
            continue
        (workspace / filename).write_text(content, encoding='utf-8')
    stack.workspace_dir = str(workspace)
    stack.save(update_fields=['workspace_dir'])
    return workspace


def _build_commands(terraform_bin, action):
    base = [terraform_bin]
    init_cmd = base + ['init', '-input=false', '-no-color']
    if action == TerraformExecution.ACTION_INIT:
        return [init_cmd]
    if action == TerraformExecution.ACTION_PLAN:
        return [init_cmd, base + ['plan', '-input=false', '-no-color']]
    if action == TerraformExecution.ACTION_APPLY:
        return [init_cmd, base + ['apply', '-input=false', '-auto-approve', '-no-color']]
    if action == TerraformExecution.ACTION_DESTROY:
        return [init_cmd, base + ['destroy', '-input=false', '-auto-approve', '-no-color']]
    raise ValueError(f'Unsupported action: {action}')


def _load_outputs(terraform_bin, workspace):
    result = subprocess.run(
        [terraform_bin, 'output', '-json'],
        cwd=workspace,
        capture_output=True,
        text=True,
        encoding='utf-8',
        errors='ignore',
        timeout=120,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return {}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {'raw': result.stdout.strip()}


def _safe_sync_apply(stack, operator):
    try:
        return sync_stack_to_cmdb(stack, operator=operator), True
    except Exception as exc:
        return {
            'detail': 'Terraform apply 成功，但自动回写 CMDB 失败，可稍后手动重试同步。',
            'error': str(exc),
        }, False


def _safe_mark_destroyed(stack):
    try:
        return mark_stack_resources_offline(stack), True
    except Exception as exc:
        return {
            'detail': 'Terraform destroy 成功，但更新 CMDB 离线状态失败。',
            'error': str(exc),
        }, False


def _finish_execution(
    stack,
    execution,
    *,
    status,
    return_code,
    stdout='',
    stderr='',
    outputs=None,
    cmdb_summary=None,
    workspace=None,
    cmdb_synced=False,
):
    now = timezone.now()
    execution.status = status
    execution.return_code = return_code
    execution.stdout = stdout or ''
    execution.stderr = stderr or ''
    execution.outputs = outputs or {}
    execution.cmdb_summary = cmdb_summary or {}
    execution.finished_at = now
    execution.save()

    update_fields = ['last_execution_status', 'last_execution_action', 'last_executed_at']
    stack.last_execution_status = status
    stack.last_execution_action = execution.action
    stack.last_executed_at = now
    if workspace:
        stack.workspace_dir = str(workspace)
        update_fields.append('workspace_dir')
    if cmdb_synced:
        stack.last_cmdb_sync_at = now
        update_fields.append('last_cmdb_sync_at')
    stack.save(update_fields=update_fields)
    return execution


def _format_command(command):
    return ' '.join(command)


def _build_command_display(commands):
    display = ' && '.join(
        ' '.join(['terraform', *command[1:]]) if command else 'terraform'
        for command in commands
    )
    return display[:255]


def _slugify(value):
    return re.sub(r'[^a-zA-Z0-9-]+', '-', str(value or '').strip()).strip('-') or 'stack'
