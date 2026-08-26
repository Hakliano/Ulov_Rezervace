"""Naplní demo sklad jednoho tenanta (lokální / staging)."""

from datetime import timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from sklad.models import (
    Alert,
    Category,
    Material,
    Recipe,
    RecipeLine,
    ServiceMapping,
    ShoppingListItem,
    StockMovement,
    Supplier,
    Tenant,
)
from sklad.services import _ensure_open_shopping, seed_units, stock_qty
from sklad.tenant import set_tenant_id


class Command(BaseCommand):
    help = 'Naplní Materiálník fiktivními daty pro demo salon.'

    def add_arguments(self, parser):
        parser.add_argument('--tenant', default='9575a447-9974-4053-8127-99cfe75f1a7c')
        parser.add_argument('--reset', action='store_true', default=True)

    def handle(self, *args, **options):
        tenant = Tenant.objects.filter(pk=options['tenant']).first()
        if not tenant:
            raise CommandError('Tenant nenalezen. Nejdřív zapněte Materiálník v partner-adminu.')
        set_tenant_id(tenant.id)
        seed_units()
        with transaction.atomic():
            if options['reset']:
                _wipe(tenant)
            _seed(tenant)
        self.stdout.write(self.style.SUCCESS(
            f'Demo sklad naplněn: {tenant.name_snapshot}'
        ))


def _wipe(tenant):
    ShoppingListItem.unscoped.filter(tenant=tenant).delete()
    Alert.unscoped.filter(tenant=tenant).delete()
    RecipeLine.unscoped.filter(tenant=tenant).delete()
    Recipe.unscoped.filter(tenant=tenant).delete()
    StockMovement.unscoped.filter(tenant=tenant).delete()
    Material.unscoped.filter(tenant=tenant).delete()
    ServiceMapping.unscoped.filter(tenant=tenant).delete()
    Category.unscoped.filter(tenant=tenant).delete()
    Supplier.unscoped.filter(tenant=tenant).delete()


def _d(value):
    return Decimal(str(value))


def _sync_catalog_mappings(tenant):
    from sklad.ulov import ulov_catalog

    services = ulov_catalog(str(tenant.id))
    for svc in services:
        ServiceMapping.objects.update_or_create(
            tenant=tenant,
            source='modernik-flow',
            external_service_id=svc['external_service_id'],
            defaults={
                'name_snapshot': svc.get('name') or '',
                'status': (
                    ServiceMapping.STAV_ACTIVE if svc.get('active', True)
                    else ServiceMapping.STAV_INACTIVE
                ),
            },
        )
    if ServiceMapping.objects.filter(tenant=tenant).exists():
        return
    # Bez napojení na Ulov ať demo pořád ukáže palety.
    for i, name in enumerate([
        'Barvení celá hlava', 'Melír fólie', 'Blond / odbarvení',
        'Střih + foukaná', 'Střih dámský', 'Keratinová kúra',
    ]):
        ServiceMapping.objects.create(
            tenant=tenant,
            source='modernik-flow',
            external_service_id=f'demo:{i + 1}',
            name_snapshot=name,
        )


def _seed(tenant):
    from sklad.models import Unit

    units = {u.code: u for u in Unit.objects.all()}
    cats = {}
    for i, name in enumerate([
        'Barvy', 'Oxidy a odbarvení', 'Péče a mytí', 'Styling', 'Spotřeba', 'Hygiena',
    ]):
        cats[name] = Category.objects.create(tenant=tenant, name=name, sort=i)

    suppliers = {}
    for name, note in [
        ('Hairservis', 'Hlavní velkoobchod, svoz každé úterý'),
        ('L\'Oréal Professionnel', 'Majirel, Serie Expert, Infinium'),
        ('Wella Professionals', 'Blondor, Color Touch, EIMI'),
        ('Kaderní centrum Brno', 'Fólie, rukavice, provozní drobnosti'),
        ('DM Profi', 'Dezinfekce a papír'),
    ]:
        suppliers[name] = Supplier.objects.create(tenant=tenant, name=name, note=note)

    specs = [
        # name, cat, supplier, unit, min, crit, price, sku, stock
        ('Barva 4.0 Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 160, 50, 189, 'MAJ-40', 220),
        ('Barva 5.0 Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 180, 60, 189, 'MAJ-50', 95),
        ('Barva 6.1 Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 240, 80, 189, 'MAJ-61', 35),
        ('Barva 6.66 Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 140, 40, 189, 'MAJ-666', 280),
        ('Barva 7.3 Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 180, 60, 189, 'MAJ-73', 420),
        ('Barva 8.1 Blond Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 200, 70, 195, 'MAJ-81', 150),
        ('Barva 9.1 Blond Majirel', 'Barvy', 'L\'Oréal Professionnel', 'ml', 160, 50, 195, 'MAJ-91', 190),
        ('Toner Dialight 9.01', 'Barvy', 'L\'Oréal Professionnel', 'ml', 120, 40, 210, 'DIA-901', 310),
        ('Toner Dialight 10.12', 'Barvy', 'L\'Oréal Professionnel', 'ml', 100, 30, 210, 'DIA-1012', 240),
        ('Oxidant 3 % L\'Oréal', 'Oxidy a odbarvení', 'L\'Oréal Professionnel', 'ml', 500, 150, 89, 'OX-3', 40),
        ('Oxidant 6 % L\'Oréal', 'Oxidy a odbarvení', 'L\'Oréal Professionnel', 'ml', 500, 150, 89, 'OX-6', 980),
        ('Oxidant 9 % L\'Oréal', 'Oxidy a odbarvení', 'L\'Oréal Professionnel', 'ml', 400, 120, 89, 'OX-9', 640),
        ('Odbarvovač Blondor', 'Oxidy a odbarvení', 'Wella Professionals', 'g', 250, 80, 420, 'BLD-1', 90),
        ('Oxycream Wella 12 %', 'Oxidy a odbarvení', 'Wella Professionals', 'ml', 300, 100, 95, 'WEL-12', 520),
        ('Šampon Absolut Repair', 'Péče a mytí', 'L\'Oréal Professionnel', 'ml', 400, 120, 310, 'SE-AR-S', 180),
        ('Šampon Volume Expert', 'Péče a mytí', 'L\'Oréal Professionnel', 'ml', 300, 100, 295, 'SE-VOL', 720),
        ('Kondicionér Absolut Repair', 'Péče a mytí', 'L\'Oréal Professionnel', 'ml', 300, 100, 340, 'SE-AR-C', 540),
        ('Maska Metal Detox', 'Péče a mytí', 'L\'Oréal Professionnel', 'ml', 200, 60, 480, 'SE-MD', 260),
        ('Olej Mythic Oil', 'Péče a mytí', 'L\'Oréal Professionnel', 'ml', 80, 25, 390, 'MYT-30', 145),
        ('Lak Infinium Extra Strong', 'Styling', 'L\'Oréal Professionnel', 'ks', 4, 1, 245, 'INF-XS', 3),
        ('Sprej Tecni.art Pli', 'Styling', 'L\'Oréal Professionnel', 'ks', 3, 1, 265, 'TA-PLI', 8),
        ('Vosk EIMI Shape Shift', 'Styling', 'Wella Professionals', 'ks', 2, 1, 220, 'EIMI-SS', 5),
        ('Fólie extra široká', 'Spotřeba', 'Kaderní centrum Brno', 'ks', 6, 2, 89, 'FOL-XL', 1),
        ('Rukavice nitril M', 'Spotřeba', 'Kaderní centrum Brno', 'ks', 4, 1, 129, 'NIT-M', 11),
        ('Límce kadeřnické', 'Spotřeba', 'Kaderní centrum Brno', 'ks', 3, 1, 45, 'LIM-100', 2),
        ('Dezinfekce nástrojů', 'Hygiena', 'DM Profi', 'ml', 250, 80, 76, 'DEZ-500', 410),
        ('Papírové ručníky', 'Hygiena', 'DM Profi', 'ks', 8, 3, 62, 'PAP-6', 6),
        ('Smartbond přísada', 'Oxidy a odbarvení', 'L\'Oréal Professionnel', 'ml', 100, 30, 520, 'SMB-1', 210),
        ('Barva Color Touch 6/7', 'Barvy', 'Wella Professionals', 'ml', 160, 50, 175, 'CT-67', 380),
        ('Šampon Color Radiance', 'Péče a mytí', 'Wella Professionals', 'ml', 300, 90, 280, 'WEL-CR', 860),
    ]

    materials = {}
    targets = {}
    for name, cat, sup, unit, min_q, crit, price, sku, stock in specs:
        m = Material.objects.create(
            tenant=tenant,
            name=name,
            category=cats[cat],
            primary_supplier=suppliers[sup],
            unit=units[unit],
            min_quantity=_d(min_q),
            critical_quantity=_d(crit),
            last_purchase_price=_d(price),
            sku=sku,
            note='Demo položka pro Studio Krása Nebezká',
        )
        materials[name] = m
        targets[name] = _d(stock)

    now = timezone.now()
    _sync_catalog_mappings(tenant)

    palettes = {
        'Barvení celá hlava': [
            ('Barva 4.0 Majirel', None),
            ('Barva 5.0 Majirel', None),
            ('Barva 6.1 Majirel', None),
            ('Barva 6.66 Majirel', None),
            ('Barva 7.3 Majirel', None),
            ('Barva 8.1 Blond Majirel', None),
            ('Barva 9.1 Blond Majirel', None),
            ('Barva Color Touch 6/7', None),
            ('Oxidant 3 % L\'Oréal', None),
            ('Oxidant 6 % L\'Oréal', None),
            ('Oxidant 9 % L\'Oréal', None),
            ('Smartbond přísada', None),
            ('Rukavice nitril M', 1),
        ],
        'Melír fólie': [
            ('Odbarvovač Blondor', None),
            ('Oxidant 6 % L\'Oréal', None),
            ('Oxidant 9 % L\'Oréal', None),
            ('Oxycream Wella 12 %', None),
            ('Toner Dialight 9.01', None),
            ('Toner Dialight 10.12', None),
            ('Smartbond přísada', None),
            ('Fólie extra široká', 1),
            ('Rukavice nitril M', 1),
        ],
        'Blond / odbarvení': [
            ('Odbarvovač Blondor', None),
            ('Oxycream Wella 12 %', None),
            ('Oxidant 9 % L\'Oréal', None),
            ('Toner Dialight 9.01', None),
            ('Toner Dialight 10.12', None),
            ('Smartbond přísada', None),
            ('Rukavice nitril M', 1),
        ],
        'Střih + foukaná': [
            ('Šampon Volume Expert', 15),
            ('Kondicionér Absolut Repair', 12),
            ('Lak Infinium Extra Strong', None),
            ('Sprej Tecni.art Pli', None),
        ],
        'Střih dámský': [
            ('Šampon Volume Expert', 15),
            ('Lak Infinium Extra Strong', None),
            ('Vosk EIMI Shape Shift', None),
        ],
        'Keratinová kúra': [
            ('Maska Metal Detox', 25),
            ('Olej Mythic Oil', 4),
            ('Kondicionér Absolut Repair', 20),
        ],
        'Manikúra': [
            ('Dezinfekce nástrojů', None),
            ('Papírové ručníky', None),
        ],
        'Pedikúra': [
            ('Dezinfekce nástrojů', None),
            ('Papírové ručníky', None),
        ],
    }

    def add_recipe(mapping, lines):
        rec = Recipe.objects.create(tenant=tenant, service_mapping=mapping, active=True)
        for mat_name, qty in lines:
            m = materials[mat_name]
            RecipeLine.objects.create(
                tenant=tenant,
                recipe=rec,
                material=m,
                quantity=_d(qty) if qty is not None else None,
                unit=m.unit,
            )

    for mapping in ServiceMapping.objects.filter(tenant=tenant).order_by('name_snapshot'):
        lines = palettes.get(mapping.name_snapshot)
        if not lines:
            continue
        add_recipe(mapping, lines)

    # Týdenní spotřeba — různé dny, ať graf žije. Nakonec srovnáme na cílový stock.
    day_plan = [
        # (days_ago, hour, actor, reason, reservation, consumes[(name, qty)])
        (6, 9, 'Eva', 'Potvrzená spotřeba', 'R-2401', [
            ('Barva 6.1 Majirel', 60), ('Oxidant 6 % L\'Oréal', 90), ('Rukavice nitril M', 1),
        ]),
        (6, 11, 'Markéta', 'Automatická spotřeba po službě', 'R-2402', [
            ('Šampon Volume Expert', 20), ('Lak Infinium Extra Strong', 1),
        ]),
        (5, 10, 'Eva', 'Potvrzená spotřeba', 'R-2408', [
            ('Odbarvovač Blondor', 40), ('Oxidant 9 % L\'Oréal', 80), ('Fólie extra široká', 1),
        ]),
        (5, 14, 'Markéta', 'Potvrzená spotřeba', 'R-2411', [
            ('Barva 7.3 Majirel', 55), ('Oxidant 6 % L\'Oréal', 80), ('Šampon Color Radiance', 18),
        ]),
        (4, 9, 'Eva', 'Potvrzená spotřeba', 'R-2415', [
            ('Barva 6.1 Majirel', 70), ('Oxidant 3 % L\'Oréal', 90), ('Smartbond přísada', 8),
        ]),
        (4, 16, 'Markéta', 'Potvrzená spotřeba', 'R-2419', [
            ('Maska Metal Detox', 25), ('Olej Mythic Oil', 4),
        ]),
        (3, 10, 'Eva', 'Potvrzená spotřeba', 'R-2422', [
            ('Barva 5.0 Majirel', 60), ('Oxidant 6 % L\'Oréal', 90),
        ]),
        (3, 13, 'Markéta', 'Automatická spotřeba po službě', 'R-2425', [
            ('Šampon Absolut Repair', 22), ('Kondicionér Absolut Repair', 18),
        ]),
        (2, 9, 'Eva', 'Potvrzená spotřeba', 'R-2430', [
            ('Odbarvovač Blondor', 50), ('Oxycream Wella 12 %', 100), ('Toner Dialight 9.01', 40),
        ]),
        (2, 15, 'Markéta', 'Potvrzená spotřeba', 'R-2433', [
            ('Barva Color Touch 6/7', 50), ('Oxidant 6 % L\'Oréal', 70),
        ]),
        (1, 10, 'Eva', 'Potvrzená spotřeba', 'R-2438', [
            ('Barva 6.1 Majirel', 65), ('Oxidant 3 % L\'Oréal', 80), ('Fólie extra široká', 1),
        ]),
        (1, 12, 'Markéta', 'Potvrzená spotřeba', 'R-2440', [
            ('Šampon Volume Expert', 18), ('Sprej Tecni.art Pli', 1),
        ]),
        (0, 9, 'Eva', 'Potvrzená spotřeba', 'R-2444', [
            ('Barva 8.1 Blond Majirel', 55), ('Oxidant 9 % L\'Oréal', 80),
        ]),
        (0, 11, 'Markéta', 'Ruční odečet', '', [
            ('Dezinfekce nástrojů', 30), ('Papírové ručníky', 1), ('Límce kadeřnické', 1),
        ]),
    ]

    consumed = {name: _d(0) for name in materials}
    for _days, _h, _a, _r, _ref, lines in day_plan:
        for mat_name, qty in lines:
            consumed[mat_name] += abs(_d(qty))
    consumed['Fólie extra široká'] += _d(1)

    for name, m in materials.items():
        opening = targets[name] + consumed.get(name, _d(0))
        mv = StockMovement.objects.create(
            tenant=tenant,
            material=m,
            quantity_delta=opening,
            unit=m.unit,
            type=StockMovement.TYP_PURCHASE,
            reason='Příjem z Hairservis — týdenní svoz',
            created_by_type='user',
            created_by_user_id='Markéta',
        )
        StockMovement.objects.filter(pk=mv.pk).update(created_at=now - timedelta(days=8, hours=3))

    for days_ago, hour, actor, reason, ref, lines in day_plan:
        when = now - timedelta(days=days_ago)
        when = when.replace(hour=hour, minute=12, second=0, microsecond=0)
        typ = (
            StockMovement.TYP_AUTO if 'Automatická' in reason
            else StockMovement.TYP_MANUAL if 'Ruční' in reason
            else StockMovement.TYP_CONFIRM
        )
        for mat_name, qty in lines:
            m = materials[mat_name]
            mv = StockMovement.objects.create(
                tenant=tenant,
                material=m,
                quantity_delta=-abs(_d(qty)),
                unit=m.unit,
                type=typ,
                reason=reason,
                reservation_ref=ref,
                created_by_type='user',
                created_by_user_id=actor,
            )
            StockMovement.objects.filter(pk=mv.pk).update(created_at=when)

    # Inventura včera — korekce fólie
    foil = materials['Fólie extra široká']
    inv = StockMovement.objects.create(
        tenant=tenant,
        material=foil,
        quantity_delta=_d(-1),
        unit=foil.unit,
        type=StockMovement.TYP_INVENTORY,
        reason='Inventura — krabice byla natržená',
        created_by_type='user',
        created_by_user_id='Markéta',
    )
    StockMovement.objects.filter(pk=inv.pk).update(created_at=now - timedelta(hours=18))

    for m in materials.values():
        _ensure_open_shopping(m, stock_qty(m))

    vosk = materials['Vosk EIMI Shape Shift']
    ShoppingListItem.objects.get_or_create(
        tenant=tenant,
        material=vosk,
        status=ShoppingListItem.STAV_OPEN,
        origin=ShoppingListItem.ORIGIN_MANUAL,
        defaults={
            'quantity_to_buy': _d(3),
            'unit': vosk.unit,
            'supplier': suppliers['Wella Professionals'],
        },
    )

    # Čerstvější časovky u alertů.
    offsets = [15, 42, 90, 180, 400, 800]
    for alert, minutes in zip(
        Alert.objects.filter(status=Alert.STAV_OPEN).order_by('id'),
        offsets,
    ):
        Alert.objects.filter(pk=alert.pk).update(created_at=now - timedelta(minutes=minutes))
