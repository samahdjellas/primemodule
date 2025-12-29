{
    'name': 'Gestion des Primes',
    'version': '1.0',
    'summary': 'Gestion des barèmes de primes',
    'category': 'Human Resources',
    'author': 'Toi',
    'depends': ['base', 'web'],
    'data': [
        'views/bareme_prime_views.xml',
        'views/types_views.xml',
        'views/ajouter_point_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'prime/static/src/js/prime.js',
            'prime/static/src/xml/prime.xml',
        ],
    },
    'installable': True,
    'application': True,
}