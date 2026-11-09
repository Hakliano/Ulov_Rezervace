"""Interní chat — pouze DB Pošťáka."""

from __future__ import annotations

from django.contrib.auth.models import User
from django.db.models import Count, Q
from django.utils.html import escape

from .chat_models import ChatZprava
from .models import Profil


def profil_telefon(user):
    try:
        return (user.profil.telefon or '').strip()
    except Profil.DoesNotExist:
        return ''


def kolegove(user):
    return (
        User.objects.filter(is_active=True)
        .exclude(pk=user.pk)
        .select_related('profil')
        .order_by('first_name', 'username')
    )


def kolegove_s_meta(user):
    unread = neprectene_podle_odesilatele(user)
    return [
        {
            'user': k,
            'neprectenych': unread.get(k.pk, 0),
            'telefon': profil_telefon(k),
        }
        for k in kolegove(user)
    ]


def pocet_neprectenych(user) -> int:
    return ChatZprava.objects.filter(prijemce=user, precteno=False).count()


def neprectene_podle_odesilatele(user):
    rows = (
        ChatZprava.objects.filter(prijemce=user, precteno=False)
        .values('odesilatel')
        .annotate(pocet=Count('id'))
    )
    return {r['odesilatel']: r['pocet'] for r in rows}


def posledni_neprectene(user, limit=5):
    return list(
        ChatZprava.objects.filter(prijemce=user, precteno=False)
        .select_related('odesilatel', 'odesilatel__profil')
        .order_by('-vytvoreno')[:limit]
    )


def konverzace(user, partner):
    if user.pk == partner.pk:
        return ChatZprava.objects.none()
    return ChatZprava.objects.filter(
        (Q(odesilatel=user, prijemce=partner) | Q(odesilatel=partner, prijemce=user))
    ).select_related('odesilatel', 'prijemce')


def muze_chatovat(user, partner) -> bool:
    return partner.is_active and user.pk != partner.pk


def oznac_prectene(user, partner):
    ChatZprava.objects.filter(prijemce=user, odesilatel=partner, precteno=False).update(precteno=True)


def odeslat(user, partner, text):
    text = (text or '').strip()
    if not text:
        raise ValueError('Prázdná zpráva.')
    if len(text) > 5000:
        raise ValueError('Zpráva je příliš dlouhá.')
    if not muze_chatovat(user, partner):
        raise ValueError('Tomuto uživateli nelze psát.')
    return ChatZprava.objects.create(odesilatel=user, prijemce=partner, text=text, precteno=False)


def bezpecny_text(text):
    return escape(text or '')
