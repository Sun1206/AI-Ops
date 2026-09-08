"""
Nginx 配置文件生成器
根据 NginxDomain 及其下属 NginxRoute 生成完整的 server block
"""
import json


def _parse_json_list(text):
    """安全解析 JSON 列表, 返回 list[dict]"""
    if not text or not text.strip():
        return []
    try:
        data = json.loads(text)
        return data if isinstance(data, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def _parse_upstream_servers(text):
    """将多行文本解析为后端地址列表"""
    if not text:
        return []
    return [line.strip() for line in text.strip().splitlines() if line.strip()]


def generate_upstream_block(domain_obj, route, index):
    """如果有多个后端地址, 生成 upstream block"""
    servers = _parse_upstream_servers(route.upstream_servers)
    if len(servers) <= 1:
        return None, servers[0] if servers else 'http://127.0.0.1:80'

    safe_domain = domain_obj.domain.replace('.', '_').replace('*', 'wc')
    safe_loc = route.location.strip('/').replace('/', '_') or 'root'
    upstream_name = f'upstream_{safe_domain}_{safe_loc}_{index}'

    lines = [f'upstream {upstream_name} {{']
    for srv in servers:
        # 去掉 http:// 前缀用于 upstream
        addr = srv.replace('http://', '').replace('https://', '')
        lines.append(f'    server {addr};')
    lines.append('}')

    return '\n'.join(lines), f'http://{upstream_name}'


def generate_location_block(route, proxy_target, indent='    '):
    """生成单个 location block"""
    lines = [f'{indent}location {route.location} {{']

    # 重定向优先
    if route.redirect_url:
        code = route.redirect_code or 301
        lines.append(f'{indent}    return {code} {route.redirect_url};')
        lines.append(f'{indent}}}')
        return '\n'.join(lines)

    # client_max_body_size
    if route.client_max_body_size:
        lines.append(f'{indent}    client_max_body_size {route.client_max_body_size};')

    # proxy_pass
    lines.append(f'{indent}    proxy_pass {proxy_target};')

    # 默认 proxy headers
    default_headers = [
        ('Host', '$host'),
        ('X-Real-IP', '$remote_addr'),
        ('X-Forwarded-For', '$proxy_add_x_forwarded_for'),
        ('X-Forwarded-Proto', '$scheme'),
    ]
    # 用户自定义 proxy_set_header 覆盖
    user_proxy_headers = _parse_json_list(route.proxy_set_headers)
    user_header_names = {h.get('name', '').lower() for h in user_proxy_headers}

    for name, value in default_headers:
        if name.lower() not in user_header_names:
            lines.append(f'{indent}    proxy_set_header {name} {value};')

    for h in user_proxy_headers:
        name = h.get('name', '')
        value = h.get('value', '')
        if name:
            lines.append(f'{indent}    proxy_set_header {name} {value};')

    # 自定义 add_header
    custom_headers = _parse_json_list(route.custom_headers)
    for h in custom_headers:
        name = h.get('name', '')
        value = h.get('value', '')
        if name:
            lines.append(f'{indent}    add_header {name} "{value}";')

    # 额外指令
    if route.extra_directives:
        for directive in route.extra_directives.strip().splitlines():
            d = directive.strip()
            if d:
                if not d.endswith(';'):
                    d += ';'
                lines.append(f'{indent}    {d}')

    lines.append(f'{indent}}}')
    return '\n'.join(lines)


def generate_domain_conf(domain_obj):
    """
    为一个 NginxDomain 生成完整的 nginx conf 文件内容
    包含 upstream blocks + server block (+ 可选 SSL server block)
    """
    routes = domain_obj.routes.filter(enabled=True).order_by('location')

    upstream_blocks = []
    location_blocks = []

    for i, route in enumerate(routes):
        upstream_block, proxy_target = generate_upstream_block(domain_obj, route, i)
        if upstream_block:
            upstream_blocks.append(upstream_block)
        location_blocks.append(generate_location_block(route, proxy_target))

    # 如果没有路由, 生成一个默认 location
    if not location_blocks:
        location_blocks.append('    location / {\n        return 404;\n    }')

    parts = []

    # upstream 定义
    if upstream_blocks:
        parts.append('\n\n'.join(upstream_blocks))
        parts.append('')

    cert = domain_obj.certificate

    # HTTP server block
    server_lines = ['server {']
    server_lines.append(f'    listen {domain_obj.listen_port};')
    server_lines.append(f'    server_name {domain_obj.domain};')
    server_lines.append('')

    if cert and domain_obj.ssl_enabled:
        # 如果启用了 SSL，HTTP 默认执行 301 跳转
        server_lines.append('    location / {')
        server_lines.append('        return 301 https://$host$request_uri;')
        server_lines.append('    }')
    else:
        for loc in location_blocks:
            server_lines.append(loc)
            server_lines.append('')

    server_lines.append('}')
    parts.append('\n'.join(server_lines))

    # SSL server block (如果关联了证书)
    cert = domain_obj.certificate
    if cert and domain_obj.ssl_enabled:
        nginx_path = domain_obj.environment.nginx_path or '/etc/nginx'
        cert_path = f'{nginx_path}/ssl/{cert.cert_filename}'
        key_path = f'{nginx_path}/ssl/{cert.key_filename}'

        ssl_lines = ['', 'server {']
        ssl_lines.append(f'    listen {domain_obj.ssl_port} ssl;')
        ssl_lines.append(f'    server_name {domain_obj.domain};')
        ssl_lines.append('')
        ssl_lines.append(f'    ssl_certificate {cert_path};')
        ssl_lines.append(f'    ssl_certificate_key {key_path};')
        ssl_lines.append('    ssl_protocols TLSv1.2 TLSv1.3;')
        ssl_lines.append('    ssl_ciphers HIGH:!aNULL:!MD5;')
        ssl_lines.append('')

        for loc in location_blocks:
            ssl_lines.append(loc)
            ssl_lines.append('')

        ssl_lines.append('}')
        parts.append('\n'.join(ssl_lines))

    return '\n'.join(parts) + '\n'

