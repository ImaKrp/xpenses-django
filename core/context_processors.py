from .models import UserProfile


def user_profile(request):
    profile = UserProfile.objects.first()
    return {'user_profile': profile}
