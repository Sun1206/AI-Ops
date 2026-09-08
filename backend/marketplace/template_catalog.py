def build_runtime_compose(service_name, image, env_lines, mount_lines, bootstrap_script, volume_names):
    env_block = '\n'.join(f'      {line}' for line in env_lines)
    mount_block = '\n'.join(f'      - {line}' for line in mount_lines)
    volume_block = '\n'.join(f'  {name}:' for name in volume_names)
    return f'''version: "3.8"
services:
  {service_name}:
    image: {image}
    container_name: sxdevops_{service_name}
    restart: always
    working_dir: "{{{{workspace}}}}"
    environment:
{env_block}
    volumes:
{mount_block}
    command: >
      sh -c '
        mkdir -p "{{{{workspace}}}}";
        {bootstrap_script}
        tail -f /dev/null
      '
    tty: true
    stdin_open: true
volumes:
{volume_block}
'''


TEMPLATES = [
    {
        'name': 'MySQL',
        'icon': 'mysql',
        'category': 'database',
        'description': '关系型数据库',
        'versions': ['8.0', '5.7'],
        'sort_order': 1,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '3306', 'required': True},
            {'key': 'root_password', 'label': 'Root 密码', 'default': 'mysql@2024', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  mysql:
    image: mysql:{{version}}
    container_name: sxdevops_mysql
    restart: always
    ports:
      - "{{port}}:3306"
    environment:
      MYSQL_ROOT_PASSWORD: "{{root_password}}"
      TZ: Asia/Shanghai
    volumes:
      - mysql_data:/var/lib/mysql
    command: --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci
volumes:
  mysql_data:
''',
    },
    {
        'name': 'Redis',
        'icon': 'redis',
        'category': 'cache',
        'description': '内存数据库 / 缓存',
        'versions': ['7.0', '6.2'],
        'sort_order': 2,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '6379', 'required': True},
            {'key': 'password', 'label': '密码', 'default': 'redis@2024', 'required': False},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  redis:
    image: redis:{{version}}-alpine
    container_name: sxdevops_redis
    restart: always
    ports:
      - "{{port}}:6379"
    command: redis-server --requirepass "{{password}}" --appendonly yes
    volumes:
      - redis_data:/data
volumes:
  redis_data:
''',
    },
    {
        'name': 'PostgreSQL',
        'icon': 'postgresql',
        'category': 'database',
        'description': '关系型数据库',
        'versions': ['16', '15', '14'],
        'sort_order': 3,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '5432', 'required': True},
            {'key': 'postgres_password', 'label': '密码', 'default': 'pg@2024', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  postgres:
    image: postgres:{{version}}
    container_name: sxdevops_postgres
    restart: always
    ports:
      - "{{port}}:5432"
    environment:
      POSTGRES_PASSWORD: "{{postgres_password}}"
      TZ: Asia/Shanghai
    volumes:
      - pg_data:/var/lib/postgresql/data
volumes:
  pg_data:
''',
    },
    {
        'name': 'MongoDB',
        'icon': 'mongodb',
        'category': 'database',
        'description': 'NoSQL 文档数据库',
        'versions': ['7.0', '6.0'],
        'sort_order': 4,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '27017', 'required': True},
            {'key': 'root_username', 'label': 'Root 用户名', 'default': 'admin', 'required': True},
            {'key': 'root_password', 'label': 'Root 密码', 'default': 'mongo@2024', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  mongodb:
    image: mongo:{{version}}
    container_name: sxdevops_mongodb
    restart: always
    ports:
      - "{{port}}:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: "{{root_username}}"
      MONGO_INITDB_ROOT_PASSWORD: "{{root_password}}"
      TZ: Asia/Shanghai
    volumes:
      - mongodb_data:/data/db
volumes:
  mongodb_data:
''',
    },
    {
        'name': 'Nginx',
        'icon': 'nginx',
        'category': 'middleware',
        'description': 'Web 服务与反向代理',
        'versions': ['1.25', '1.24'],
        'sort_order': 5,
        'env_schema': [
            {'key': 'http_port', 'label': 'HTTP 端口', 'default': '80', 'required': True},
            {'key': 'https_port', 'label': 'HTTPS 端口', 'default': '443', 'required': False},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  nginx:
    image: nginx:{{version}}
    container_name: sxdevops_nginx
    restart: always
    ports:
      - "{{http_port}}:80"
      - "{{https_port}}:443"
    volumes:
      - nginx_conf:/etc/nginx/conf.d
      - nginx_html:/usr/share/nginx/html
volumes:
  nginx_conf:
  nginx_html:
''',
    },
    {
        'name': 'Jenkins',
        'icon': 'jenkins',
        'category': 'cicd',
        'description': '持续集成 / 持续部署',
        'versions': ['lts', 'latest'],
        'sort_order': 6,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '8080', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  jenkins:
    image: jenkins/jenkins:{{version}}
    container_name: sxdevops_jenkins
    restart: always
    ports:
      - "{{port}}:8080"
      - "50000:50000"
    volumes:
      - jenkins_home:/var/jenkins_home
    environment:
      TZ: Asia/Shanghai
volumes:
  jenkins_home:
''',
    },
    {
        'name': 'GitLab',
        'icon': 'gitlab',
        'category': 'cicd',
        'description': '代码托管平台',
        'versions': ['latest', '16.8'],
        'sort_order': 7,
        'env_schema': [
            {'key': 'http_port', 'label': 'HTTP 端口', 'default': '8929', 'required': True},
            {'key': 'ssh_port', 'label': 'SSH 端口', 'default': '2224', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  gitlab:
    image: gitlab/gitlab-ce:{{version}}
    container_name: sxdevops_gitlab
    restart: always
    ports:
      - "{{http_port}}:80"
      - "{{ssh_port}}:22"
    volumes:
      - gitlab_config:/etc/gitlab
      - gitlab_logs:/var/log/gitlab
      - gitlab_data:/var/opt/gitlab
    shm_size: "256m"
volumes:
  gitlab_config:
  gitlab_logs:
  gitlab_data:
''',
    },
    {
        'name': 'Grafana',
        'icon': 'grafana',
        'category': 'monitoring',
        'description': '可视化面板',
        'versions': ['latest', '10.3'],
        'sort_order': 8,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '3000', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  grafana:
    image: grafana/grafana:{{version}}
    container_name: sxdevops_grafana
    restart: always
    ports:
      - "{{port}}:3000"
    volumes:
      - grafana_data:/var/lib/grafana
    environment:
      TZ: Asia/Shanghai
volumes:
  grafana_data:
''',
    },
    {
        'name': 'Elasticsearch',
        'icon': 'elasticsearch',
        'category': 'monitoring',
        'description': '搜索引擎',
        'versions': ['8.12', '7.17'],
        'sort_order': 9,
        'env_schema': [
            {'key': 'port', 'label': 'HTTP 端口', 'default': '9200', 'required': True},
            {'key': 'java_opts', 'label': 'JVM 参数', 'default': '-Xms512m -Xmx512m', 'required': False},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:{{version}}.0
    container_name: sxdevops_elasticsearch
    restart: always
    ports:
      - "{{port}}:9200"
    environment:
      - discovery.type=single-node
      - ES_JAVA_OPTS={{java_opts}}
      - xpack.security.enabled=false
      - TZ=Asia/Shanghai
    volumes:
      - es_data:/usr/share/elasticsearch/data
volumes:
  es_data:
''',
    },
    {
        'name': 'Loki',
        'icon': 'loki',
        'category': 'monitoring',
        'description': '日志聚合系统',
        'versions': ['2.9.4', '2.8.0'],
        'sort_order': 10,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '3100', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  loki:
    image: grafana/loki:{{version}}
    container_name: sxdevops_loki
    restart: always
    ports:
      - "{{port}}:3100"
    command: -config.file=/etc/loki/local-config.yaml
    volumes:
      - loki_data:/loki
volumes:
  loki_data:
''',
    },
    {
        'name': 'JumpServer',
        'icon': 'jumpserver',
        'category': 'security',
        'description': '开源堡垒机',
        'versions': ['latest', 'v3.10'],
        'sort_order': 11,
        'env_schema': [
            {'key': 'port', 'label': 'HTTP 端口', 'default': '80', 'required': True},
            {'key': 'secret_key', 'label': 'Secret Key', 'default': 'sxdevops_jumpserver_secret', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  jumpserver:
    image: jumpserver/jms_all:{{version}}
    container_name: sxdevops_jumpserver
    restart: always
    ports:
      - "{{port}}:80"
      - "2222:2222"
    environment:
      SECRET_KEY: "{{secret_key}}"
      BOOTSTRAP_TOKEN: "{{secret_key}}"
      TZ: Asia/Shanghai
    volumes:
      - js_data:/opt/jumpserver/data
volumes:
  js_data:
''',
    },
    {
        'name': 'Nacos',
        'icon': 'nacos',
        'category': 'middleware',
        'description': '注册中心 / 配置中心',
        'versions': ['v2.3.0', 'v2.2.3', 'latest'],
        'sort_order': 12,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '8848', 'required': True},
            {'key': 'mode', 'label': '运行模式', 'default': 'standalone', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  nacos:
    image: nacos/nacos-server:{{version}}
    container_name: sxdevops_nacos
    restart: always
    ports:
      - "{{port}}:8848"
      - "9848:9848"
      - "9849:9849"
    environment:
      MODE: "{{mode}}"
      TZ: Asia/Shanghai
    volumes:
      - nacos_logs:/home/nacos/logs
volumes:
  nacos_logs:
''',
    },
    {
        'name': 'XXL-Job',
        'icon': 'xxljob',
        'category': 'middleware',
        'description': '分布式任务调度平台',
        'versions': ['2.4.0', '2.3.1'],
        'sort_order': 13,
        'env_schema': [
            {'key': 'port', 'label': '端口', 'default': '8088', 'required': True},
            {'key': 'db_host', 'label': 'MySQL 地址', 'default': '127.0.0.1', 'required': True},
            {'key': 'db_port', 'label': 'MySQL 端口', 'default': '3306', 'required': True},
            {'key': 'db_user', 'label': 'MySQL 用户', 'default': 'root', 'required': True},
            {'key': 'db_password', 'label': 'MySQL 密码', 'default': 'root', 'required': True},
        ],
        'docker_compose_template': '''version: "3.8"
services:
  xxl-job-admin:
    image: xuxueli/xxl-job-admin:{{version}}
    container_name: sxdevops_xxljob
    restart: always
    ports:
      - "{{port}}:8080"
    environment:
      PARAMS: >-
        --spring.datasource.url=jdbc:mysql://{{db_host}}:{{db_port}}/xxl_job?useUnicode=true&characterEncoding=UTF-8&autoReconnect=true&serverTimezone=Asia/Shanghai
        --spring.datasource.username={{db_user}}
        --spring.datasource.password={{db_password}}
      TZ: Asia/Shanghai
    volumes:
      - xxljob_data:/data/applogs
volumes:
  xxljob_data:
''',
    },
    {
        'name': 'Java',
        'icon': 'java',
        'category': 'devenv',
        'description': '常用 Java + Maven 开发运行环境',
        'versions': ['3.9.9-eclipse-temurin-21', '3.9.9-eclipse-temurin-17'],
        'sort_order': 14,
        'env_schema': [
            {'key': 'workspace', 'label': '工作目录', 'default': '/workspace', 'required': True},
            {'key': 'maven_mirror_url', 'label': 'Maven 镜像源', 'default': 'https://maven.aliyun.com/repository/public', 'required': False},
            {'key': 'maven_opts', 'label': 'Maven 参数', 'default': '-Xms256m -Xmx512m', 'required': False},
        ],
        'docker_compose_template': build_runtime_compose(
            'java',
            'maven:{{version}}',
            [
                'TZ: Asia/Shanghai',
                'MAVEN_MIRROR_URL: "{{maven_mirror_url}}"',
                'MAVEN_OPTS: "{{maven_opts}}"',
            ],
            [
                'java_workspace:{{workspace}}',
                'java_m2:/root/.m2',
            ],
            'if [ -n "$MAVEN_MIRROR_URL" ]; then mkdir -p /root/.m2 && cat >/root/.m2/settings.xml <<EOF\n<settings>\n  <mirrors>\n    <mirror>\n      <id>custom</id>\n      <mirrorOf>*</mirrorOf>\n      <url>$MAVEN_MIRROR_URL</url>\n    </mirror>\n  </mirrors>\n</settings>\nEOF\n; fi;',
            ['java_workspace', 'java_m2'],
        ),
    },
    {
        'name': 'Python',
        'icon': 'python',
        'category': 'devenv',
        'description': '常用 Python 运行环境',
        'versions': ['3.12', '3.11'],
        'sort_order': 15,
        'env_schema': [
            {'key': 'workspace', 'label': '工作目录', 'default': '/workspace', 'required': True},
            {'key': 'pip_index_url', 'label': 'PIP 镜像源', 'default': 'https://pypi.tuna.tsinghua.edu.cn/simple', 'required': False},
            {'key': 'pip_trusted_host', 'label': 'PIP 信任域名', 'default': 'pypi.tuna.tsinghua.edu.cn', 'required': False},
        ],
        'docker_compose_template': build_runtime_compose(
            'python',
            'python:{{version}}',
            [
                'TZ: Asia/Shanghai',
                'PIP_INDEX_URL: "{{pip_index_url}}"',
                'PIP_TRUSTED_HOST: "{{pip_trusted_host}}"',
            ],
            [
                'python_workspace:{{workspace}}',
                'python_pip_cache:/root/.cache/pip',
            ],
            'if [ -n "$PIP_INDEX_URL" ]; then pip config set global.index-url "$PIP_INDEX_URL"; fi; if [ -n "$PIP_TRUSTED_HOST" ]; then pip config set global.trusted-host "$PIP_TRUSTED_HOST"; fi;',
            ['python_workspace', 'python_pip_cache'],
        ),
    },
    {
        'name': 'Go',
        'icon': 'go',
        'category': 'devenv',
        'description': '常用 Go 运行环境',
        'versions': ['1.22', '1.21'],
        'sort_order': 16,
        'env_schema': [
            {'key': 'workspace', 'label': '工作目录', 'default': '/workspace', 'required': True},
            {'key': 'go_proxy', 'label': 'Go 代理', 'default': 'https://goproxy.cn,direct', 'required': False},
        ],
        'docker_compose_template': build_runtime_compose(
            'go',
            'golang:{{version}}',
            [
                'TZ: Asia/Shanghai',
                'GOPROXY: "{{go_proxy}}"',
                'GOMODCACHE: /go/pkg/mod',
                'GOCACHE: /root/.cache/go-build',
            ],
            [
                'go_workspace:{{workspace}}',
                'go_mod_cache:/go/pkg/mod',
                'go_build_cache:/root/.cache/go-build',
            ],
            'if [ -n "$GOPROXY" ]; then go env -w GOPROXY="$GOPROXY"; fi;',
            ['go_workspace', 'go_mod_cache', 'go_build_cache'],
        ),
    },
    {
        'name': 'Node.js',
        'icon': 'nodejs',
        'category': 'devenv',
        'description': '常用 Node.js 运行环境',
        'versions': ['20', '18'],
        'sort_order': 17,
        'env_schema': [
            {'key': 'workspace', 'label': '工作目录', 'default': '/workspace', 'required': True},
            {'key': 'npm_registry', 'label': 'NPM 镜像源', 'default': 'https://registry.npmmirror.com', 'required': False},
        ],
        'docker_compose_template': build_runtime_compose(
            'nodejs',
            'node:{{version}}',
            [
                'TZ: Asia/Shanghai',
                'NPM_CONFIG_REGISTRY: "{{npm_registry}}"',
                'COREPACK_ENABLE_DOWNLOAD_PROMPT: "0"',
            ],
            [
                'nodejs_workspace:{{workspace}}',
                'nodejs_npm_cache:/root/.npm',
                'nodejs_pnpm_store:/root/.local/share/pnpm/store',
            ],
            'if [ -n "$NPM_CONFIG_REGISTRY" ]; then npm config set registry "$NPM_CONFIG_REGISTRY"; corepack enable >/dev/null 2>&1 || true; fi;',
            ['nodejs_workspace', 'nodejs_npm_cache', 'nodejs_pnpm_store'],
        ),
    },
]
