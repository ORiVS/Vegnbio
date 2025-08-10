# utils.py
from django.core.mail import send_mail
from django.conf import settings

def send_invite_email(invite, base_url):
    subject = f"Invitation à l'évènement {invite.event.title}"
    link = f"{base_url}/events/invite/accept?token={invite.token}"
    message = (
        f"Bonjour,\n\n"
        f"Vous êtes invité(e) à l'évènement '{invite.event.title}' le {invite.event.date} "
        f"de {invite.event.start_time} à {invite.event.end_time}.\n\n"
        f"Pour accepter l'invitation : {link}\n\n"
        f"À bientôt."
    )
    if invite.email:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [invite.email], fail_silently=True)

def notify_event_published(event):
    # prévenir des inscrits potentiels,
    pass

def notify_event_cancelled(event):
    from .models import EvenementRegistration
    subject = f"[Annulation] {event.title}"
    message = (
        f"L'évènement '{event.title}' du {event.date} est annulé.\n"
        f"Nous vous prions de nous excuser pour la gêne occasionnée."
    )
    recipients = list(
        event.registrations.select_related('user').values_list('user__email', flat=True)
    )
    if recipients:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients, fail_silently=True)

def notify_event_full(event):
    #  prévenir l’orga/owner
    pass
