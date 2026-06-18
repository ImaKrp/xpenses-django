from . import repository
from .supabase_client import user_schema


def user_profile(request):
    if not request.user.is_authenticated:
        return {'user_profile': None}
    schema = user_schema(request.user.id)
    profile = repository.get_profile(schema)
    return {'user_profile': profile}
