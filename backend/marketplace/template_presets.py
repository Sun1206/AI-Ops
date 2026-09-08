def _quoted(value):
    return f'"{value}"'


def build_k8s_manifest(
    name,
    image,
    ports,
    env=None,
    workload='Deployment',
    volume_mount='',
    args=None,
    command=None,
    include_service=True,
    extra_volume_mounts=None,
    volume_claim_templates=None,
):
    env = env or {}
    args = args or []
    extra_volume_mounts = extra_volume_mounts or []
    volume_claim_templates = volume_claim_templates or []
    name_slug = name.lower().replace(' ', '-')
    is_stateful = workload == 'StatefulSet'
    lines = [
        'apiVersion: apps/v1',
        f'kind: {workload}',
        'metadata:',
        '  name: {{release_name}}',
        'spec:',
    ]
    if is_stateful:
        lines.append('  serviceName: {{release_name}}')
    lines.extend([
        '  replicas: {{replicas}}',
        '  selector:',
        '    matchLabels:',
        '      app: {{release_name}}',
        '  template:',
        '    metadata:',
        '      labels:',
        '        app: {{release_name}}',
        '    spec:',
        '      containers:',
        f'        - name: {name_slug}',
        f'          image: {image}',
    ])

    if ports:
        lines.append('          ports:')
        for port in ports:
            lines.append(f'            - containerPort: {port["target_port"]}')

    if env:
        lines.append('          env:')
        for key, value in env.items():
            lines.append(f'            - name: {key}')
            lines.append(f'              value: {_quoted(value)}')

    if args:
        lines.append('          args:')
        for item in args:
            lines.append(f'            - {_quoted(item)}')

    if command:
        lines.append('          command:')
        for item in command:
            lines.append(f'            - {_quoted(item)}')

    if volume_mount:
        lines.extend([
            '          volumeMounts:',
            '            - name: data',
            f'              mountPath: {volume_mount}',
        ])
        for extra_mount in extra_volume_mounts:
            lines.extend([
                f'            - name: {extra_mount["name"]}',
                f'              mountPath: {extra_mount["mount_path"]}',
            ])
        if is_stateful:
            lines.extend([
                '  volumeClaimTemplates:',
                '    - metadata:',
                '        name: data',
                '      spec:',
                '        accessModes: ["ReadWriteOnce"]',
                '        resources:',
                '          requests:',
                '            storage: 10Gi',
            ])
        else:
            lines.extend([
                '      volumes:',
                '        - name: data',
                '          emptyDir: {}',
            ])
    if volume_claim_templates:
        if not is_stateful:
            lines.extend([
                '      volumes:',
            ])
            for claim in volume_claim_templates:
                lines.extend([
                    f'        - name: {claim["name"]}',
                    '          persistentVolumeClaim:',
                    f'            claimName: {claim["name"]}',
                ])
        else:
            if '  volumeClaimTemplates:' not in lines:
                lines.append('  volumeClaimTemplates:')
            for claim in volume_claim_templates:
                lines.extend([
                    '    - metadata:',
                    f'        name: {claim["name"]}',
                    '      spec:',
                    '        accessModes: ["ReadWriteOnce"]',
                    '        resources:',
                    '          requests:',
                    f'            storage: {claim.get("storage", "10Gi")}',
                ])

    if include_service:
        lines.extend([
            '---',
            'apiVersion: v1',
            'kind: Service',
            'metadata:',
            '  name: {{release_name}}',
            'spec:',
            '  selector:',
            '    app: {{release_name}}',
            '  ports:',
        ])
        for port in ports:
            lines.extend([
                f'    - name: {port["name"]}',
                f'      port: {port["port"]}',
                f'      targetPort: {port["target_port"]}',
            ])
    return '\n'.join(lines) + '\n'


def build_runtime_k8s_manifest(name, image, env=None, command=None, pvc_mounts=None):
    env = env or {}
    command = command or ['sh', '-c', 'tail -f /dev/null']
    pvc_mounts = pvc_mounts or []
    deployment_name = name.lower().replace(' ', '-')

    lines = []
    for pvc in pvc_mounts:
        lines.extend([
            'apiVersion: v1',
            'kind: PersistentVolumeClaim',
            'metadata:',
            f'  name: {{{{release_name}}}}-{pvc["name"]}',
            'spec:',
            '  accessModes:',
            '    - ReadWriteOnce',
            '  resources:',
            '    requests:',
            f'      storage: {pvc.get("storage", "5Gi")}',
            '---',
        ])

    lines.extend([
        'apiVersion: apps/v1',
        'kind: Deployment',
        'metadata:',
        '  name: {{release_name}}',
        'spec:',
        '  replicas: {{replicas}}',
        '  selector:',
        '    matchLabels:',
        '      app: {{release_name}}',
        '  template:',
        '    metadata:',
        '      labels:',
        '        app: {{release_name}}',
        '    spec:',
        '      containers:',
        f'        - name: {deployment_name}',
        f'          image: {image}',
    ])

    if env:
        lines.append('          env:')
        for key, value in env.items():
            lines.extend([
                f'            - name: {key}',
                f'              value: {_quoted(value)}',
            ])

    if command:
        lines.append('          command:')
        for item in command:
            lines.append(f'            - {_quoted(item)}')

    if pvc_mounts:
        lines.append('          volumeMounts:')
        for pvc in pvc_mounts:
            lines.extend([
                f'            - name: {pvc["name"]}',
                f'              mountPath: {pvc["mount_path"]}',
            ])
        lines.append('      volumes:')
        for pvc in pvc_mounts:
            lines.extend([
                f'        - name: {pvc["name"]}',
                '          persistentVolumeClaim:',
                f'            claimName: {{{{release_name}}}}-{pvc["name"]}',
            ])

    return '\n'.join(lines) + '\n'


K8S_MANIFESTS = {
    'MySQL': build_k8s_manifest(
        'mysql',
        'mysql:{{version}}',
        [{'name': 'mysql', 'port': '{{port}}', 'target_port': 3306}],
        env={'MYSQL_ROOT_PASSWORD': '{{root_password}}', 'TZ': 'Asia/Shanghai'},
        workload='StatefulSet',
        volume_mount='/var/lib/mysql',
    ),
    'Redis': build_k8s_manifest(
        'redis',
        'redis:{{version}}-alpine',
        [{'name': 'redis', 'port': '{{port}}', 'target_port': 6379}],
        workload='StatefulSet',
        volume_mount='/data',
        args=['--requirepass', '{{password}}', '--appendonly', 'yes'],
    ),
    'PostgreSQL': build_k8s_manifest(
        'postgresql',
        'postgres:{{version}}',
        [{'name': 'postgres', 'port': '{{port}}', 'target_port': 5432}],
        env={'POSTGRES_PASSWORD': '{{postgres_password}}', 'TZ': 'Asia/Shanghai'},
        workload='StatefulSet',
        volume_mount='/var/lib/postgresql/data',
    ),
    'MongoDB': build_k8s_manifest(
        'mongodb',
        'mongo:{{version}}',
        [{'name': 'mongodb', 'port': '{{port}}', 'target_port': 27017}],
        env={
            'MONGO_INITDB_ROOT_USERNAME': '{{root_username}}',
            'MONGO_INITDB_ROOT_PASSWORD': '{{root_password}}',
            'TZ': 'Asia/Shanghai',
        },
        workload='StatefulSet',
        volume_mount='/data/db',
    ),
    'Nginx': build_k8s_manifest(
        'nginx',
        'nginx:{{version}}',
        [
            {'name': 'http', 'port': '{{http_port}}', 'target_port': 80},
            {'name': 'https', 'port': '{{https_port}}', 'target_port': 443},
        ],
        volume_mount='/usr/share/nginx/html',
    ),
    'Jenkins': build_k8s_manifest(
        'jenkins',
        'jenkins/jenkins:{{version}}',
        [
            {'name': 'http', 'port': '{{port}}', 'target_port': 8080},
            {'name': 'agent', 'port': 50000, 'target_port': 50000},
        ],
        env={'TZ': 'Asia/Shanghai'},
        volume_mount='/var/jenkins_home',
    ),
    'GitLab': build_k8s_manifest(
        'gitlab',
        'gitlab/gitlab-ce:{{version}}',
        [
            {'name': 'http', 'port': '{{http_port}}', 'target_port': 80},
            {'name': 'ssh', 'port': '{{ssh_port}}', 'target_port': 22},
        ],
        volume_mount='/var/opt/gitlab',
    ),
    'Grafana': build_k8s_manifest(
        'grafana',
        'grafana/grafana:{{version}}',
        [{'name': 'http', 'port': '{{port}}', 'target_port': 3000}],
        env={'TZ': 'Asia/Shanghai'},
        volume_mount='/var/lib/grafana',
    ),
    'Elasticsearch': build_k8s_manifest(
        'elasticsearch',
        'docker.elastic.co/elasticsearch/elasticsearch:{{version}}.0',
        [{'name': 'http', 'port': '{{port}}', 'target_port': 9200}],
        env={'ES_JAVA_OPTS': '{{java_opts}}', 'TZ': 'Asia/Shanghai'},
        args=['-Ediscovery.type=single-node', '-Expack.security.enabled=false'],
        volume_mount='/usr/share/elasticsearch/data',
    ),
    'Loki': build_k8s_manifest(
        'loki',
        'grafana/loki:{{version}}',
        [{'name': 'http', 'port': '{{port}}', 'target_port': 3100}],
        args=['-config.file=/etc/loki/local-config.yaml'],
        volume_mount='/loki',
    ),
    'JumpServer': build_k8s_manifest(
        'jumpserver',
        'jumpserver/jms_all:{{version}}',
        [
            {'name': 'http', 'port': '{{port}}', 'target_port': 80},
            {'name': 'ssh', 'port': 2222, 'target_port': 2222},
        ],
        env={
            'SECRET_KEY': '{{secret_key}}',
            'BOOTSTRAP_TOKEN': '{{secret_key}}',
            'TZ': 'Asia/Shanghai',
        },
        volume_mount='/opt/jumpserver/data',
    ),
    'Nacos': build_k8s_manifest(
        'nacos',
        'nacos/nacos-server:{{version}}',
        [
            {'name': 'http', 'port': '{{port}}', 'target_port': 8848},
            {'name': 'raft', 'port': 9848, 'target_port': 9848},
            {'name': 'grpc', 'port': 9849, 'target_port': 9849},
        ],
        env={'MODE': '{{mode}}', 'TZ': 'Asia/Shanghai'},
        volume_mount='/home/nacos/logs',
    ),
    'XXL-Job': build_k8s_manifest(
        'xxljob',
        'xuxueli/xxl-job-admin:{{version}}',
        [{'name': 'http', 'port': '{{port}}', 'target_port': 8080}],
        env={
            'PARAMS': (
                '--spring.datasource.url=jdbc:mysql://{{db_host}}:{{db_port}}/xxl_job?'
                'useUnicode=true&characterEncoding=UTF-8&autoReconnect=true&serverTimezone=Asia/Shanghai '
                '--spring.datasource.username={{db_user}} '
                '--spring.datasource.password={{db_password}}'
            ),
            'TZ': 'Asia/Shanghai',
        },
        volume_mount='/data/applogs',
    ),
    'Java': build_runtime_k8s_manifest(
        'java',
        'maven:{{version}}',
        env={
            'TZ': 'Asia/Shanghai',
            'MAVEN_MIRROR_URL': '{{maven_mirror_url}}',
            'MAVEN_OPTS': '{{maven_opts}}',
        },
        command=[
            'sh',
            '-c',
            'mkdir -p {{workspace}} /root/.m2 && '
            'if [ -n "$MAVEN_MIRROR_URL" ]; then cat >/root/.m2/settings.xml <<EOF\n'
            '<settings>\n'
            '  <mirrors>\n'
            '    <mirror>\n'
            '      <id>custom</id>\n'
            '      <mirrorOf>*</mirrorOf>\n'
            '      <url>$MAVEN_MIRROR_URL</url>\n'
            '    </mirror>\n'
            '  </mirrors>\n'
            '</settings>\n'
            'EOF\n'
            'fi && tail -f /dev/null',
        ],
        pvc_mounts=[
            {'name': 'workspace', 'mount_path': '{{workspace}}', 'storage': '10Gi'},
            {'name': 'm2-cache', 'mount_path': '/root/.m2', 'storage': '5Gi'},
        ],
    ),
    'Python': build_runtime_k8s_manifest(
        'python',
        'python:{{version}}',
        env={
            'TZ': 'Asia/Shanghai',
            'PIP_INDEX_URL': '{{pip_index_url}}',
            'PIP_TRUSTED_HOST': '{{pip_trusted_host}}',
        },
        command=[
            'sh',
            '-c',
            'mkdir -p {{workspace}} /root/.cache/pip && '
            'if [ -n "$PIP_INDEX_URL" ]; then pip config set global.index-url "$PIP_INDEX_URL"; fi && '
            'if [ -n "$PIP_TRUSTED_HOST" ]; then pip config set global.trusted-host "$PIP_TRUSTED_HOST"; fi && '
            'tail -f /dev/null',
        ],
        pvc_mounts=[
            {'name': 'workspace', 'mount_path': '{{workspace}}', 'storage': '10Gi'},
            {'name': 'pip-cache', 'mount_path': '/root/.cache/pip', 'storage': '5Gi'},
        ],
    ),
    'Go': build_runtime_k8s_manifest(
        'go',
        'golang:{{version}}',
        env={
            'TZ': 'Asia/Shanghai',
            'GOPROXY': '{{go_proxy}}',
            'GOMODCACHE': '/go/pkg/mod',
            'GOCACHE': '/root/.cache/go-build',
        },
        command=[
            'sh',
            '-c',
            'mkdir -p {{workspace}} /go/pkg/mod /root/.cache/go-build && '
            'if [ -n "$GOPROXY" ]; then go env -w GOPROXY="$GOPROXY"; fi && '
            'tail -f /dev/null',
        ],
        pvc_mounts=[
            {'name': 'workspace', 'mount_path': '{{workspace}}', 'storage': '10Gi'},
            {'name': 'gomod-cache', 'mount_path': '/go/pkg/mod', 'storage': '5Gi'},
            {'name': 'gobuild-cache', 'mount_path': '/root/.cache/go-build', 'storage': '5Gi'},
        ],
    ),
    'Node.js': build_runtime_k8s_manifest(
        'nodejs',
        'node:{{version}}',
        env={
            'TZ': 'Asia/Shanghai',
            'NPM_CONFIG_REGISTRY': '{{npm_registry}}',
            'COREPACK_ENABLE_DOWNLOAD_PROMPT': '0',
        },
        command=[
            'sh',
            '-c',
            'mkdir -p {{workspace}} /root/.npm /root/.local/share/pnpm/store && '
            'if [ -n "$NPM_CONFIG_REGISTRY" ]; then npm config set registry "$NPM_CONFIG_REGISTRY"; fi && '
            'corepack enable >/dev/null 2>&1 || true && '
            'tail -f /dev/null',
        ],
        pvc_mounts=[
            {'name': 'workspace', 'mount_path': '{{workspace}}', 'storage': '10Gi'},
            {'name': 'npm-cache', 'mount_path': '/root/.npm', 'storage': '5Gi'},
            {'name': 'pnpm-store', 'mount_path': '/root/.local/share/pnpm/store', 'storage': '5Gi'},
        ],
    ),
}
