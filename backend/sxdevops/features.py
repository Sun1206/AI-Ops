def permission_feature_enabled(code):
    return True


def tool_feature_enabled(name):
    return True


def filter_feature_permissions(codes):
    return list(codes or [])


def filter_feature_tools(names):
    return list(names or [])
