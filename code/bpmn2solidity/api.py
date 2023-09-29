from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from rest_framework.authtoken.views import obtain_auth_token, ObtainAuthToken

# automatically create tokens for newly created users

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_auth_token(sender, instance=None, created=False, **kwargs):
    if created:
        Token.objects.create(user=instance)


#def choen_login(*args, **kwargs):
#    return obtain_auth_token(*args, **kwargs)


class ChoenAuthToken(ObtainAuthToken):
    authentication_classes = ()
