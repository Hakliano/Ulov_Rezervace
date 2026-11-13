"""Demonstrační scénáře pro technické testování (ne obchodní texty)."""

from phone_scripts.constants import ALL_BRANCH_KEYS, Product, branch_key
from phone_scripts.constants import SalesStyle, WebStatus


def _shared_demo_graph(product: str) -> dict:
    product_label = 'Moderník' if product == Product.MODERNIK else 'HereYouAre'
    areas = {
        'uvod': {'slug': 'uvod', 'name': 'Úvod', 'sortOrder': 0, 'entryStepId': 'uvod_1'},
        'rezervace': {'slug': 'rezervace', 'name': 'Rezervace', 'sortOrder': 1, 'entryStepId': 'rez_1'},
        'zaver': {'slug': 'zaver', 'name': 'Závěr', 'sortOrder': 2, 'entryStepId': 'end_1'},
    }
    steps = {
        'uvod_1': {
            'type': 'question',
            'areaSlug': 'uvod',
            'say': 'Dobrý den, u telefonu {agent_name} z ULOV KLIENTY. '
            f'Volám ohledně {product_label}. Máte chvilku?',
            'goal': 'Ověřit zájem pokračovat.',
            'answers': [
                {'label': 'Ano, mám čas', 'targetStepId': 'probe_1', 'sortOrder': 0},
                {'label': 'Ne, nemám čas', 'targetStepId': 'polite_1', 'sortOrder': 1},
            ],
        },
        'probe_1': {
            'type': 'question',
            'areaSlug': 'uvod',
            'say': 'Jak dnes zákazníci u vás typicky objednávají služby nebo termíny?',
            'goal': 'Zjistit rezervační kanál.',
            'answers': [
                {'label': 'Telefonicky', 'targetStepId': 'rez_1', 'sortOrder': 0},
                {'label': 'Online', 'targetStepId': 'rez_2', 'sortOrder': 1},
                {'label': 'Kombinace', 'targetStepId': 'rez_1', 'sortOrder': 2},
            ],
        },
        'rez_1': {
            'type': 'question',
            'areaSlug': 'rezervace',
            'say': 'Přerušuje vás telefon během práce často?',
            'goal': 'Zjistit dopad telefonátů.',
            'answers': [
                {'label': 'Ano, často', 'targetStepId': 'need_1', 'sortOrder': 0},
                {'label': 'Spíš ne', 'targetStepId': 'end_ok', 'sortOrder': 1},
            ],
        },
        'rez_2': {
            'type': 'question',
            'areaSlug': 'rezervace',
            'say': 'Jste se současným online systémem spokojeni?',
            'goal': 'Zjistit spokojenost.',
            'answers': [
                {'label': 'Ano', 'targetStepId': 'end_ok', 'sortOrder': 0},
                {'label': 'Ne úplně', 'targetStepId': 'need_1', 'sortOrder': 1},
            ],
        },
        'need_1': {
            'type': 'question',
            'areaSlug': 'rezervace',
            'say': 'Kdybyste mohli jednu věc zlepšit, co by to bylo?',
            'goal': 'Najít konkrétní potřebu.',
            'answers': [
                {'label': 'Méně telefonátů', 'targetStepId': 'offer_1', 'sortOrder': 0},
                {'label': 'Lepší přehled', 'targetStepId': 'offer_1', 'sortOrder': 1},
                {'label': 'Nic', 'targetStepId': 'end_ok', 'sortOrder': 2},
            ],
        },
        'offer_1': {
            'type': 'pricing',
            'areaSlug': 'zaver',
            'say': f'{product_label} umí online prezentaci a rezervace. '
            'Cenu řeknu až když dává smysl — chcete ji teď slyšet?',
            'goal': 'Nabídnout cenu až na žádost.',
            'answers': [
                {'label': 'Ano, kolik to stojí', 'targetStepId': 'price_1', 'sortOrder': 0},
                {'label': 'Raději ukázku', 'targetStepId': 'close_demo', 'sortOrder': 1},
                {'label': 'Teď ne', 'targetStepId': 'end_ok', 'sortOrder': 2},
            ],
        },
        'price_1': {
            'type': 'info',
            'areaSlug': 'zaver',
            'say': 'Tarif START od 299 Kč měsíčně plus aktivace. '
            'Detaily pošleme e-mailem, pokud budete chtít.',
            'goal': 'Transparentní cena.',
            'answers': [{'label': 'Děkuji', 'targetStepId': 'close_info', 'sortOrder': 0}],
        },
        'close_demo': {
            'type': 'closing',
            'areaSlug': 'zaver',
            'say': 'Domluvíme krátkou ukázku na čas, který vám vyhovuje?',
            'goal': 'Domluva ukázky.',
            'answers': [{'label': 'Ano', 'targetStepId': 'end_hot', 'sortOrder': 0}],
        },
        'close_info': {
            'type': 'closing',
            'areaSlug': 'zaver',
            'say': 'Pošlu stručné informace a ozvu se za pár dní, jestli to bude aktuální.',
            'goal': 'Domluva follow-up.',
            'answers': [{'label': 'Souhlas', 'targetStepId': 'end_hot', 'sortOrder': 0}],
        },
        'end_ok': {
            'type': 'closing',
            'areaSlug': 'zaver',
            'say': 'Děkuji za upřímnost. Kdyby se situace změnila, jsem k dispozici. Hezký den.',
            'goal': 'Přirozené ukončení.',
            'answers': [{'label': 'Ukončit', 'endCall': True, 'sortOrder': 0}],
        },
        'end_hot': {
            'type': 'closing',
            'areaSlug': 'zaver',
            'say': 'Skvělé, domluvíme detaily e-mailem. Děkuji a hezký den.',
            'goal': 'Pozitivní závěr.',
            'answers': [{'label': 'Ukončit', 'endCall': True, 'sortOrder': 0}],
        },
        'polite_1': {
            'type': 'polite_exit',
            'areaSlug': 'uvod',
            'say': 'Rozumím, nebudu vás zdržovat. Kdybyste měli zájem později, ozvěte se. Hezký den.',
            'goal': 'Zdvořilé ukončení.',
            'answers': [{'label': 'Ukončit', 'endCall': True, 'sortOrder': 0}],
        },
    }

    branch_entries = {}
    for web in WebStatus.values:
        for style in SalesStyle.values:
            entry = 'entry_has' if web == WebStatus.HAS_WEB else 'entry_no' if web == WebStatus.NO_WEB else 'entry_unk'
            if style == SalesStyle.DYNAMIC:
                entry += '_dyn'
            steps[entry] = {
                'type': 'question',
                'areaSlug': 'uvod',
                'say': _branch_say(web, style, product_label),
                'goal': 'Vstup dle známého kontextu.',
                'answers': [{'label': 'Pokračovat', 'targetStepId': 'uvod_1', 'sortOrder': 0}],
            }
            branch_entries[branch_key(web, style)] = entry

    objections = {
        'drahe': {
            'slug': 'drahe',
            'title': 'Je to drahé',
            'sortOrder': 0,
            'rootStepId': 'obj_price',
            'responses': [
                {
                    'say': 'Rozumím, rozpočet je důležitý. Mrkneme na to v kontextu vašich ztrát času?',
                    'returnOnly': False,
                    'targetStepId': 'need_1',
                    'sortOrder': 0,
                },
            ],
        },
        'nema_cas': {
            'slug': 'nema_cas',
            'title': 'Nemám čas',
            'sortOrder': 1,
            'responses': [
                {
                    'say': 'Díky, zkusím to velmi stručně — jedna otázka?',
                    'returnOnly': True,
                    'sortOrder': 0,
                },
            ],
        },
        'nevolejte': {
            'slug': 'nevolejte',
            'title': 'Už mi nevolejte',
            'sortOrder': 2,
            'responses': [
                {
                    'say': 'Omlouvám se za nepříjemnost. Už vás nebudu kontaktovat. Hezký den.',
                    'hardReject': True,
                    'sortOrder': 0,
                },
            ],
        },
    }
    steps['obj_price'] = {
        'type': 'question',
        'areaSlug': 'zaver',
        'say': 'Porovnáváte spíš s jinou službou, nebo je problém v celkovém rozpočtu?',
        'goal': 'Zjištění kontextu námitky ceny.',
        'answers': [
            {'label': 'Konkurence', 'targetStepId': 'price_1', 'sortOrder': 0},
            {'label': 'Rozpočet', 'targetStepId': 'end_ok', 'sortOrder': 1},
        ],
    }

    return {
        'meta': {
            'slug': f'demo-{product}',
            'name': f'Demo {product_label}',
            'product': product,
        },
        'areas': areas,
        'steps': steps,
        'initialBranches': branch_entries,
        'openings': [
            {
                'name': 'Standard',
                'text': 'Dobrý den, u telefonu {agent_name}, ULOV KLIENTY.',
                'sortOrder': 0,
            }
        ],
        'objections': objections,
        'pricing': [
            {
                'productName': 'START',
                'monthlyCzk': 299,
                'activationCzk': 1999,
                'description': 'Demo ceník',
                'sortOrder': 0,
            },
        ],
    }


def _branch_say(web: str, style: str, product_label: str) -> str:
    base = {
        WebStatus.HAS_WEB: f'Vidím, že máte vlastní web — u {product_label} ověřím, jak vám slouží.',
        WebStatus.NO_WEB: f'U vás zatím nevidím vlastní web — u {product_label} to může být příležitost.',
        WebStatus.UNKNOWN: 'Nejdřív bych rychle ověřil, jestli máte vlastní web.',
    }[web]
    if style == SalesStyle.DYNAMIC:
        return base + ' Půjdeme na to přímo.'
    return base + ' Půjdeme na to v klidu krok za krokem.'


def demo_modernik_payload() -> dict:
    return _shared_demo_graph(Product.MODERNIK)


def demo_hya_payload() -> dict:
    return _shared_demo_graph(Product.HEREYOUARE)


def build_stress_payload(slug: str = 'stress-test', steps_count: int = 180) -> dict:
    areas = {
        'load': {'slug': 'load', 'name': 'Zátěžový test', 'sortOrder': 0, 'entryStepId': 's000'},
    }
    steps = {}
    for i in range(steps_count):
        sid = f's{i:03d}'
        next_id = f's{(i + 1):03d}' if i + 1 < steps_count else 's_end'
        steps[sid] = {
            'type': 'question',
            'areaSlug': 'load',
            'say': f'[TEST] Krok {i + 1}/{steps_count}: ukázková věta pro telefonistu.',
            'goal': f'Cíl testovacího kroku {i + 1}.',
            'answers': [
                {'label': 'Další krok', 'targetStepId': next_id, 'sortOrder': 0},
                {'label': 'Zpětní větev', 'targetStepId': f's{max(0, i - 1):03d}', 'sortOrder': 1},
            ],
        }
    steps['s_end'] = {
        'type': 'closing',
        'areaSlug': 'load',
        'say': '[TEST] Konec zátěžového scénáře.',
        'goal': 'Ukončení.',
        'answers': [{'label': 'Konec', 'endCall': True, 'sortOrder': 0}],
    }
    branches = {key: 's000' for key in ALL_BRANCH_KEYS}
    return {
        'meta': {'slug': slug, 'name': 'Zátěžový test', 'product': Product.MODERNIK},
        'areas': areas,
        'steps': steps,
        'initialBranches': branches,
        'openings': [],
        'objections': {
            'test': {
                'slug': 'test',
                'title': 'Test námitka',
                'sortOrder': 0,
                'responses': [{'say': '[TEST] Odpověď na námitku.', 'returnOnly': True, 'sortOrder': 0}],
            },
        },
        'pricing': [],
    }
