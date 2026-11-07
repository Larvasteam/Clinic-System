def user_roles(user):
    """Names of the groups a user belongs to; superusers count as Admin."""
    if not user.is_authenticated:
        return set()
    if user.is_superuser:
        return {'Admin'}
    return set(user.groups.values_list('name', flat=True))
