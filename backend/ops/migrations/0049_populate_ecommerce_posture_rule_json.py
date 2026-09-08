from django.db import migrations


ECOMMERCE_SERVICES = [
    {
        'id': 'api-gateway',
        'name': 'API 网关',
        'role': '入口层',
        'target_ms': 500,
        'paths': [
            {'id': 'gateway-checkout', 'name': 'POST /api/checkout', 'path': '/api/checkout', 'target_ms': 500, 'hint': '下单入口，成功率来自 checkout outcome 业务指标。'},
            {'id': 'gateway-cart-add', 'name': 'POST /api/cart/<user_id>/items', 'path': '/api/cart/<user_id>/items', 'target_ms': 300, 'hint': '加购入口，联动 catalog 与 cart 服务。'},
            {'id': 'gateway-cart-query', 'name': 'GET /api/cart/<user_id>', 'path': '/api/cart/<user_id>', 'target_ms': 250, 'hint': '购物车查询，联动 cart 与 Redis。'},
            {'id': 'gateway-products', 'name': 'GET /api/products', 'path': '/api/products', 'target_ms': 350, 'hint': '商品浏览入口，联动 catalog 与 inventory。'},
        ],
    },
    {
        'id': 'cart',
        'name': '购物车服务',
        'role': '交易前置',
        'target_ms': 250,
        'paths': [
            {'id': 'cart-add', 'name': 'POST /cart/<user_id>/items', 'path': '/cart/<user_id>/items', 'target_ms': 180, 'hint': '购物车写入接口，依赖 Redis。'},
            {'id': 'cart-query', 'name': 'GET /cart/<user_id>', 'path': '/cart/<user_id>', 'target_ms': 120, 'hint': '购物车读取接口，依赖 Redis。'},
        ],
    },
    {
        'id': 'order',
        'name': '订单服务',
        'role': '交易核心',
        'target_ms': 450,
        'paths': [
            {'id': 'order-create', 'name': 'POST /orders', 'path': '/orders', 'target_ms': 350, 'hint': '订单创建接口，依赖 inventory、PostgreSQL 与 Kafka。'},
        ],
    },
    {
        'id': 'inventory',
        'name': '库存服务',
        'role': '履约校验',
        'target_ms': 250,
        'paths': [
            {'id': 'inventory-availability', 'name': 'POST /availability', 'path': '/availability', 'target_ms': 160, 'hint': '库存可用性检查，直接影响下单成功率。'},
        ],
    },
    {
        'id': 'catalog',
        'name': '商品服务',
        'role': '商品读取',
        'target_ms': 250,
        'paths': [
            {'id': 'catalog-list', 'name': 'GET /products', 'path': '/products', 'target_ms': 180, 'hint': '商品列表接口。'},
            {'id': 'catalog-detail', 'name': 'GET /products/<int:product_id>', 'path': '/products/<int:product_id>', 'target_ms': 180, 'hint': '商品详情接口，加购前置依赖。'},
        ],
    },
]


ECOMMERCE_DEPENDENCIES = [
    {'id': 'postgres', 'name': 'PostgreSQL', 'role': 'downstream', 'kind': '数据库', 'impact': '订单写入与库存查询异常会直接影响下单。'},
    {'id': 'redis', 'name': 'Redis', 'role': 'downstream', 'kind': '缓存', 'impact': '购物车读写依赖 Redis，异常会阻断下单前置流程。'},
    {'id': 'kafka', 'name': 'Kafka', 'role': 'downstream', 'kind': '消息队列', 'impact': '订单事件写入 Kafka，异常会影响库存异步扣减。'},
]


def populate_ecommerce_posture_rule_json(apps, schema_editor):
    SystemPostureSystem = apps.get_model('ops', 'SystemPostureSystem')
    queryset = SystemPostureSystem.objects.filter(name__in=['电商交易核心', '交易系统核心'])
    for system in queryset:
        rule_config = system.rule_config if isinstance(system.rule_config, dict) else {}
        prometheus = rule_config.get('prometheus') if isinstance(rule_config.get('prometheus'), dict) else {}
        scalars = prometheus.get('scalars') if isinstance(prometheus.get('scalars'), dict) else {}
        core_metric = rule_config.get('core_metric') if isinstance(rule_config.get('core_metric'), dict) else {}
        if 'checkout_success_rate' not in scalars and core_metric.get('metric') != 'checkout_success_rate':
            continue

        next_config = dict(rule_config)
        next_config.setdefault('core_metric', {
            'metric': 'runtime_availability',
            'label': '环境可用率',
            'target': 90,
            'unit': '%',
            'direction': 'higher',
        })

        rules = next_config.get('root_cause_rules')
        if not isinstance(rules, list) or not rules:
            rules = [{'id': 'inventory-conflict', 'metric': 'checkout_conflict_rate', 'target_service_id': 'inventory'}]
        normalized_rules = []
        seen_inventory_rule = False
        for rule in rules:
            if not isinstance(rule, dict):
                normalized_rules.append(rule)
                continue
            next_rule = dict(rule)
            if next_rule.get('id') == 'inventory-conflict' or next_rule.get('target_service_id') == 'inventory':
                seen_inventory_rule = True
                next_rule.setdefault('id', 'inventory-conflict')
                next_rule.setdefault('label', '库存冲突')
                next_rule.setdefault('metric', 'checkout_conflict_rate')
                next_rule.setdefault('min_rate', 1)
                next_rule.setdefault('critical_rate', 1)
                next_rule.setdefault('min_rps', 0.001)
                next_rule['count_as_fault'] = True
                next_rule.setdefault('target_service_id', 'inventory')
                next_rule.setdefault('target_interface_id', 'inventory-availability')
                next_rule.setdefault('affected_services', [
                    {
                        'service_id': 'api-gateway',
                        'interface_id': 'gateway-checkout',
                        'metric_label': 'Checkout 409占比',
                        'message': '下单入口返回 409，需要继续下钻库存与订单链路。',
                    },
                    {
                        'service_id': 'order',
                        'interface_id': 'order-create',
                        'metric_label': '订单受影响',
                        'message': '订单创建被库存冲突拒绝，需要核对订单写入前后的库存校验。',
                    },
                    {
                        'service_id': 'inventory',
                        'interface_id': 'inventory-availability',
                        'metric_label': '库存冲突率',
                        'message': '库存可用性校验返回冲突，优先检查库存余量与补货任务。',
                    },
                ])
                next_rule.setdefault('metric_label', '库存冲突率')
            normalized_rules.append(next_rule)
        if not seen_inventory_rule:
            normalized_rules.append({
                'id': 'inventory-conflict',
                'label': '库存冲突',
                'metric': 'checkout_conflict_rate',
                'min_rate': 1,
                'critical_rate': 1,
                'min_rps': 0.001,
                'count_as_fault': True,
                'target_service_id': 'inventory',
                'target_interface_id': 'inventory-availability',
                'affected_services': [
                    {
                        'service_id': 'api-gateway',
                        'interface_id': 'gateway-checkout',
                        'metric_label': 'Checkout 409占比',
                        'message': '下单入口返回 409，需要继续下钻库存与订单链路。',
                    },
                    {
                        'service_id': 'order',
                        'interface_id': 'order-create',
                        'metric_label': '订单受影响',
                        'message': '订单创建被库存冲突拒绝，需要核对订单写入前后的库存校验。',
                    },
                    {
                        'service_id': 'inventory',
                        'interface_id': 'inventory-availability',
                        'metric_label': '库存冲突率',
                        'message': '库存可用性校验返回冲突，优先检查库存余量与补货任务。',
                    },
                ],
                'metric_label': '库存冲突率',
            })
        next_config['root_cause_rules'] = normalized_rules

        drilldown = next_config.get('drilldown') if isinstance(next_config.get('drilldown'), dict) else {}
        next_drilldown = dict(drilldown)
        if not isinstance(next_drilldown.get('services'), list) or not next_drilldown.get('services'):
            next_drilldown['services'] = ECOMMERCE_SERVICES
        if not isinstance(next_drilldown.get('dependencies'), list) or not next_drilldown.get('dependencies'):
            next_drilldown['dependencies'] = ECOMMERCE_DEPENDENCIES
        next_config['drilldown'] = next_drilldown

        system.rule_config = next_config
        system.save(update_fields=['rule_config'])


class Migration(migrations.Migration):

    dependencies = [
        ('ops', '0048_rename_systemposture_north_star_verbose'),
    ]

    operations = [
        migrations.RunPython(populate_ecommerce_posture_rule_json, migrations.RunPython.noop),
    ]
