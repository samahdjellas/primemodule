from odoo import models, fields, api


class BaremePrime(models.Model):
    _name = 'bareme.prime'
    _description = 'Barème de Prime'

    name = fields.Char(
        string='Nom',
        required=True
    )
    zone_id = fields.Many2one(
        'zone',
        string='Zone',
        required=True
    )
    type = fields.Selection(
        [
            ('pourcentage', 'Pourcentage'),
            ('coefficient', 'coefficient'),
        ],
        string='Type de prime',
        required=True,
        default='pourcentage'
    )

    valeur_pourcentage = fields.Integer(
        string='Valeur (%)'
    )

    coefficient = fields.Integer(
        string='coefficient'
    )

    def action_test_agents_zones(self):
        """Méthode appelée par le bouton de test"""
        self.get_all_agents_with_zones()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test terminé',
                'message': 'Vérifiez la console du navigateur pour voir les résultats',
                'sticky': False,
                'type': 'info'
            }
        }

    def get_all_agents_with_zones(self):
        users = self.env['res.users'].search([])

        print("===== AGENTS & ZONES =====")

        for user in users:
            if user.zone_ids:
                for zone in user.zone_ids:
                    print(f"{{ {user.name} , {zone.name} }}")
            else:
                print(f"{{ {user.name} , Aucune zone }}")

        print("==========================")

    def get_agents_lavage_count(self):
        """Affiche pour chaque agent combien de lavages il a fait"""
        users = self.env['res.users'].search([])
        Depense = self.env['depense.record']

        print("===== LAVAGES PAR AGENT =====")

        for user in users:
            lavage_count = Depense.search_count([
                ('caisse.user_id', '=', user.id),
                ('type_depense', '=', 1),
                ('status', '=', 'valide'),
            ])
            print(f"{user.name}")
            print(f"{{ lavage : {lavage_count} }}")

        print("============================")

    def action_test_lavages(self):
        self.get_agents_lavage_count()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test lavages terminé',
                'message': 'Vérifiez la console serveur pour les résultats',
                'sticky': False,
                'type': 'info'
            }
        }

    def get_agents_livraison_stats(self):
        """Calcule pour chaque agent les statistiques de départs et retours"""
        users = self.env['res.users'].search([])
        Livraison = self.env['livraison']

        print("===== STATISTIQUES LIVRAISONS PAR AGENT =====")

        for user in users:
            # Récupérer les zones de l'agent
            agent_zones = user.zone_ids

            # Récupérer TOUTES les livraisons (départs + retours)
            livraisons = Livraison.search([
                ('livrer_par', '=', user.id),
                ('stage', '=', 'livre')
            ])

            livraison_normal = 0
            livraison_hors_zone = 0
            livraison_tardif = 0

            for livraison in livraisons:
                # Vérifier si tardif (entre 19h et 07h)
                if livraison.date_de_livraison:
                    heure = livraison.date_de_livraison.hour
                    is_tardif = heure >= 19 or heure < 7
                else:
                    is_tardif = False

                # Vérifier si hors zone selon le type
                is_hors_zone = False
                if livraison.lv_type == 'livraison':
                    # Pour un DÉPART: vérifier le lieu_depart
                    if livraison.lieu_depart and livraison.lieu_depart.zone:
                        is_hors_zone = livraison.lieu_depart.zone not in agent_zones
                elif livraison.lv_type == 'restitution':
                    # Pour un RETOUR: vérifier le lieu_retour
                    if livraison.lieu_retour and livraison.lieu_retour.zone:
                        is_hors_zone = livraison.lieu_retour.zone not in agent_zones

                # Compter selon la catégorie
                if is_tardif:
                    livraison_tardif += 1
                elif is_hors_zone:
                    livraison_hors_zone += 1
                else:
                    livraison_normal += 1

            # Afficher les résultats
            print(
                f"{user.name} {{ (livraison normal : {livraison_normal}) (livraison hors zone : {livraison_hors_zone}) (livraison tardive : {livraison_tardif}) }}")

        print("=============================================")

    def action_test_livraison_stats(self):
        """Action pour tester les statistiques de livraisons"""
        self.get_agents_livraison_stats()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test statistiques terminé',
                'message': 'Vérifiez la console serveur pour les résultats',
                'sticky': False,
                'type': 'info'
            }
        }

    def get_agents_degradation_stats(self):
        """Affiche pour chaque agent le nombre de retours avec dégradation et le total"""
        users = self.env['res.users'].search([])
        Livraison = self.env['livraison']

        print("===== DÉGRADATIONS PAR AGENT =====")

        for user in users:
            # Récupérer tous les retours validés de l'agent
            retours_avec_degradation = Livraison.search([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'restitution'),
                ('stage', '=', 'livre'),
                ('degradation_limit_da', '>', 0)
            ])

            nombre_retours = len(retours_avec_degradation)
            total_degradation = sum(retour.degradation_limit_da for retour in retours_avec_degradation)

            print(f"{user.name} {{ {nombre_retours} , {total_degradation:.2f} }}")

        print("==================================")

    def action_test_degradations(self):
        """Action pour tester les statistiques de dégradations"""
        self.get_agents_degradation_stats()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test dégradations terminé',
                'message': 'Vérifiez la console serveur pour les résultats',
                'sticky': False,
                'type': 'info'
            }
        }

    def get_agents_maintenance_alert_count(self):
        """Affiche pour chaque agent combien de maintenances et d'alertes il a créées"""
        users = self.env['res.users'].search([])
        Maintenance = self.env['maintenance.record']

        print("===== MAINTENANCES & ALERTES PAR AGENT =====")

        for user in users:
            # Compter les maintenances (alert_id vide)
            maintenance_count = Maintenance.search_count([
                ('create_uid', '=', user.id),
                ('alert_id', '=', False)
            ])

            # Compter les alertes (alert_id rempli)
            alert_count = Maintenance.search_count([
                ('create_uid', '=', user.id),
                ('alert_id', '!=', False)
            ])

            print(f"{user.name} {{ maintenance : {maintenance_count} , alert : {alert_count} }}")

        print("============================================")

    def action_test_maintenance_alert(self):
        """Action pour tester les statistiques de maintenances et alertes"""
        self.get_agents_maintenance_alert_count()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test maintenances/alertes terminé',
                'message': 'Vérifiez la console serveur pour les résultats',
                'sticky': False,
                'type': 'info'
            }
        }

    def get_agents_ventes_options(self):
        """Affiche pour chaque agent les options vendues lors des départs"""
        users = self.env['res.users'].search([])
        Livraison = self.env['livraison']

        print("===== VENTES D'OPTIONS PAR AGENT =====")

        for user in users:
            # Récupérer toutes les livraisons (départs) validées de l'agent
            livraisons_depart = Livraison.search([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'livraison'),
                ('stage', '=', 'livre')
            ])

            # Compter chaque option
            siege_bebe_count = 0
            nd_driver_count = 0
            carburant_count = 0
            standart_count = 0
            max_count = 0

            for livraison in livraisons_depart:
                if livraison.sb_ajout:
                    siege_bebe_count += 1
                if livraison.nd_driver_ajoute:
                    nd_driver_count += 1
                if livraison.carburant_ajoute:
                    carburant_count += 1
                if livraison.standart_ajoute:
                    standart_count += 1
                if livraison.max_ajoute:
                    max_count += 1

            # Construire l'affichage dynamique (n'afficher que les options > 0)
            options_vendues = []
            if siege_bebe_count > 0:
                options_vendues.append(f"siege bebe : {siege_bebe_count}")
            if nd_driver_count > 0:
                options_vendues.append(f"2eme conducteur : {nd_driver_count}")
            if carburant_count > 0:
                options_vendues.append(f"carburant : {carburant_count}")
            if standart_count > 0:
                options_vendues.append(f"protection standard : {standart_count}")
            if max_count > 0:
                options_vendues.append(f"protection max : {max_count}")

            # Afficher uniquement si au moins une option vendue
            if options_vendues:
                options_str = " , ".join(options_vendues)
                print(f"{user.name} {{ {options_str} }}")
            else:
                print(f"{user.name} {{ aucune option vendue }}")

        print("======================================")

    def action_test_ventes_options(self):
        """Action pour tester les ventes d'options"""
        self.get_agents_ventes_options()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Test ventes options terminé',
                'message': 'Vérifiez la console serveur pour les résultats',
                'sticky': False,
                'type': 'info'
            }
        }

    def calculate_agent_points(self):
        """Calcule les points de chaque agent selon les barèmes de type coefficient"""
        users = self.env['res.users'].search([])
        Livraison = self.env['livraison']
        Depense = self.env['depense.record']
        Maintenance = self.env['maintenance.record']

        # Récupérer tous les barèmes de type coefficient
        baremes = self.search([('type', '=', 'coefficient')])

        results = []  # ← NOUVEAU : stocker les résultats

        for user in users:
            total_points = 0
            details = {}  # ← Changer de liste à dict pour faciliter l'accès
            agent_zones = user.zone_ids

            # Dictionnaire pour stocker les comptes déjà traités
            processed_stats = {}

            # ... (tout ton code de calcul reste identique) ...
            # LAVAGES
            processed_stats['lavage'] = Depense.search_count([
                ('caisse.user_id', '=', user.id),
                ('type_depense', '=', 1),
                ('status', '=', 'valide'),
            ])

            # LIVRAISONS
            livraisons = Livraison.search([
                ('livrer_par', '=', user.id),
                ('stage', '=', 'livre')
            ])

            processed_stats['livraison_normal'] = 0
            processed_stats['livraison_hors_zone'] = 0
            processed_stats['livraison_tardive'] = 0

            for lv in livraisons:
                is_tardif = False
                is_hors_zone = False

                if lv.date_de_livraison:
                    heure = lv.date_de_livraison.hour
                    is_tardif = heure >= 19 or heure < 7

                if lv.lv_type == 'livraison' and lv.lieu_depart and lv.lieu_depart.zone:
                    is_hors_zone = lv.lieu_depart.zone not in agent_zones
                elif lv.lv_type == 'restitution' and lv.lieu_retour and lv.lieu_retour.zone:
                    is_hors_zone = lv.lieu_retour.zone not in agent_zones

                if is_tardif:
                    processed_stats['livraison_tardive'] += 1
                elif is_hors_zone:
                    processed_stats['livraison_hors_zone'] += 1
                else:
                    processed_stats['livraison_normal'] += 1

            # OPTIONS VENDUES
            processed_stats['siege_bebe'] = Livraison.search_count([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'livraison'),
                ('stage', '=', 'livre'),
                ('sb_ajout', '=', True)
            ])

            processed_stats['conducteur'] = Livraison.search_count([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'livraison'),
                ('stage', '=', 'livre'),
                ('nd_driver_ajoute', '=', True)
            ])

            processed_stats['carburant'] = Livraison.search_count([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'livraison'),
                ('stage', '=', 'livre'),
                ('carburant_ajoute', '=', True)
            ])

            processed_stats['protection_standard'] = Livraison.search_count([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'livraison'),
                ('stage', '=', 'livre'),
                ('standart_ajoute', '=', True)
            ])

            processed_stats['protection_max'] = Livraison.search_count([
                ('livrer_par', '=', user.id),
                ('lv_type', '=', 'livraison'),
                ('stage', '=', 'livre'),
                ('max_ajoute', '=', True)
            ])

            # MAINTENANCES ET ALERTES
            processed_stats['maintenance'] = Maintenance.search_count([
                ('create_uid', '=', user.id),
                ('alert_id', '=', False)
            ])

            processed_stats['alerte'] = Maintenance.search_count([
                ('create_uid', '=', user.id),
                ('alert_id', '!=', False)
            ])

            # Appliquer les barèmes
            bareme_mapping = {}

            for bareme in baremes:
                bareme_name = bareme.name.lower()
                stat_key = None

                # Mapping PRÉCIS et EXCLUSIF (ton code existant)
                if 'lavage' in bareme_name:
                    stat_key = 'lavage'
                elif 'livraison normal' in bareme_name or 'livraison zone' in bareme_name or 'livraison/restitution' in bareme_name:
                    stat_key = 'livraison_normal'
                elif 'hors zone' in bareme_name or 'hors_zone' in bareme_name:
                    stat_key = 'livraison_hors_zone'
                elif 'tardif' in bareme_name or 'tardive' in bareme_name:
                    stat_key = 'livraison_tardive'
                elif 'maintenance' in bareme_name and 'alert' not in bareme_name:
                    stat_key = 'maintenance'
                elif 'alert' in bareme_name:
                    stat_key = 'alerte'
                elif 'siege' in bareme_name or 'bebe' in bareme_name or 'siège' in bareme_name:
                    stat_key = 'siege_bebe'
                elif '2eme conducteur' in bareme_name or '2ème conducteur' in bareme_name or (
                        'conducteur' in bareme_name and '2' not in bareme_name
                ):
                    stat_key = 'conducteur'
                elif 'carburant' in bareme_name:
                    stat_key = 'carburant'
                elif 'protection standard' in bareme_name or (
                        'standard' in bareme_name and 'protection' in bareme_name
                ):
                    stat_key = 'protection_standard'
                elif 'protection max' in bareme_name or (
                        'max' in bareme_name and 'protection' in bareme_name
                ):
                    stat_key = 'protection_max'

                # Appliquer le barème
                if stat_key and stat_key not in bareme_mapping:
                    bareme_mapping[stat_key] = bareme
                    count = processed_stats.get(stat_key, 0)

                    if count > 0:
                        points = count * bareme.coefficient
                        total_points += points
                        details[stat_key] = {
                            'count': count,
                            'coefficient': bareme.coefficient,
                            'points': points,
                            'bareme_name': bareme.name
                        }

            # ← NOUVEAU : Ajouter les résultats de cet agent
            results.append({
                'user_id': user.id,
                'user_name': user.name,
                'total_points': total_points,
                'details': details
            })

        # ← NOUVEAU : Retourner les résultats
        return results
    def action_calculate_points(self):
        """Action pour calculer les points des agents"""
        self.calculate_agent_points()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Calcul des points terminé',
                'message': 'Vérifiez la console serveur pour les résultats détaillés',
                'sticky': False,
                'type': 'success'
            }
        }

    def calculate_manual_points_prime(self):
        """Calcule les primes des points ajoutés manuellement selon les barèmes"""
        users = self.env['res.users'].search([])
        AjouterPoint = self.env['ajouter.point']

        results = []  # ← NOUVEAU : stocker les résultats

        for user in users:
            total_prime = 0
            details = {}  # ← Changer de liste à dict
            agent_zones = user.zone_ids

            # Récupérer tous les points ajoutés pour cet utilisateur
            points_ajoutes = AjouterPoint.search([('user_id', '=', user.id)])

            for point in points_ajoutes:
                # Chercher le barème correspondant au type et à la zone de l'agent
                bareme = None

                # D'abord chercher un barème spécifique à une zone de l'agent
                for zone in agent_zones:
                    bareme = self.search([
                        ('name', '=', point.type_id.name),
                        ('zone_id', '=', zone.id),
                        ('type', '=', 'coefficient')
                    ], limit=1)
                    if bareme:
                        break

                # Si pas trouvé, chercher un barème sans zone spécifique
                if not bareme:
                    bareme = self.search([
                        ('name', '=', point.type_id.name),
                        ('zone_id', '=', False),
                        ('type', '=', 'coefficient')
                    ], limit=1)

                # Calculer la prime si barème trouvé
                if bareme:
                    prime = point.nombre * bareme.coefficient
                    total_prime += prime

                    # ← NOUVEAU : Stocker dans un dict avec le nom du type comme clé
                    type_key = point.type_id.name.lower().replace(' ', '_')

                    # Si ce type existe déjà, additionner
                    if type_key in details:
                        details[type_key]['count'] += point.nombre
                        details[type_key]['points'] += prime
                    else:
                        details[type_key] = {
                            'count': point.nombre,
                            'coefficient': bareme.coefficient,
                            'points': prime,
                            'bareme_name': point.type_id.name
                        }
                else:
                    # Type non trouvé
                    type_key = point.type_id.name.lower().replace(' ', '_')
                    if type_key not in details:
                        details[type_key] = {
                            'count': point.nombre,
                            'coefficient': 0,
                            'points': 0,
                            'bareme_name': point.type_id.name + ' (Non trouvé)'
                        }

            # ← NOUVEAU : Ajouter les résultats de cet agent
            results.append({
                'user_id': user.id,
                'user_name': user.name,
                'total_prime': total_prime,
                'details': details
            })

        # ← NOUVEAU : Retourner les résultats
        return results

    def action_calculate_manual_prime(self):
        """Action pour calculer les primes des points manuels"""
        self.calculate_manual_points_prime()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Calcul des primes terminé',
                'message': 'Vérifiez la console serveur pour les résultats',
                'sticky': False,
                'type': 'success'
            }
        }

    def get_agent_detailed_stats(self, user_id):
        """Retourne les statistiques détaillées d'un agent"""
        user = self.env['res.users'].browse(user_id)
        Livraison = self.env['livraison']
        Depense = self.env['depense.record']
        Maintenance = self.env['maintenance.record']

        agent_zones = user.zone_ids
        stats = {}

        # LAVAGES
        lavage_count = Depense.search_count([
            ('caisse.user_id', '=', user.id),
            ('type_depense', '=', 1),
            ('status', '=', 'valide'),
        ])
        stats['lavage'] = lavage_count

        # LIVRAISONS
        livraisons = Livraison.search([
            ('livrer_par', '=', user.id),
            ('stage', '=', 'livre')
        ])

        stats['livraison_normal'] = 0
        stats['livraison_hors_zone'] = 0
        stats['livraison_tardive'] = 0

        for lv in livraisons:
            is_tardif = False
            is_hors_zone = False

            # Vérifier si tardif
            if lv.date_de_livraison:
                heure = lv.date_de_livraison.hour
                is_tardif = heure >= 19 or heure < 7

            # Vérifier si hors zone
            if lv.lv_type == 'livraison' and lv.lieu_depart and lv.lieu_depart.zone:
                is_hors_zone = lv.lieu_depart.zone not in agent_zones
            elif lv.lv_type == 'restitution' and lv.lieu_retour and lv.lieu_retour.zone:
                is_hors_zone = lv.lieu_retour.zone not in agent_zones

            # Compter les livraisons
            if is_tardif:
                stats['livraison_tardive'] += 1
            elif is_hors_zone:
                stats['livraison_hors_zone'] += 1
            else:
                stats['livraison_normal'] += 1

        # OPTIONS VENDUES
        stats['siege_bebe'] = Livraison.search_count([
            ('livrer_par', '=', user.id),
            ('lv_type', '=', 'livraison'),
            ('stage', '=', 'livre'),
            ('sb_ajout', '=', True)
        ])

        stats['conducteur'] = Livraison.search_count([
            ('livrer_par', '=', user.id),
            ('lv_type', '=', 'livraison'),
            ('stage', '=', 'livre'),
            ('nd_driver_ajoute', '=', True)
        ])

        stats['carburant'] = Livraison.search_count([
            ('livrer_par', '=', user.id),
            ('lv_type', '=', 'livraison'),
            ('stage', '=', 'livre'),
            ('carburant_ajoute', '=', True)
        ])

        stats['protection_standard'] = Livraison.search_count([
            ('livrer_par', '=', user.id),
            ('lv_type', '=', 'livraison'),
            ('stage', '=', 'livre'),
            ('standart_ajoute', '=', True)
        ])

        stats['protection_max'] = Livraison.search_count([
            ('livrer_par', '=', user.id),
            ('lv_type', '=', 'livraison'),
            ('stage', '=', 'livre'),
            ('max_ajoute', '=', True)
        ])

        # MAINTENANCES ET ALERTES
        stats['maintenance'] = Maintenance.search_count([
            ('create_uid', '=', user.id),
            ('alert_id', '=', False)
        ])

        stats['alerte'] = Maintenance.search_count([
            ('create_uid', '=', user.id),
            ('alert_id', '!=', False)
        ])

        return stats

    def action_get_agent_stats(self):
        """Action pour tester les statistiques d'un agent"""
        # Test avec le premier utilisateur
        users = self.env['res.users'].search([], limit=1)
        if users:
            stats = self.get_agent_detailed_stats(users[0].id)
            print("===== STATISTIQUES DÉTAILLÉES =====")
            for key, value in stats.items():
                print(f"{key}: {value}")
            print("=================================")

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Statistiques calculées',
                'message': 'Vérifiez la console serveur',
                'sticky': False,
                'type': 'info'
            }
        }

    def calculate_agent_points_with_ranking(self):
        """Calcule les points + détermine le Premier National ET Premier Régional"""

        # 1. Calculer les points internes
        internal_results = self.calculate_agent_points()

        # 2. Calculer les primes manuelles
        manual_results = self.calculate_manual_points_prime()

        # 3. Calculer la prime totale pour chaque agent
        agents_with_total_prime = []

        for internal in internal_results:
            # Trouver les points manuels correspondants
            manual = next((m for m in manual_results if m['user_id'] == internal['user_id']), None)

            # Calculer la prime totale
            prime_services = internal['total_points'] * 100  # Points × 100 DA
            prime_speciale = manual['total_prime'] if manual else 0
            prime_totale = prime_services + prime_speciale

            # Récupérer l'utilisateur pour avoir ses zones
            user = self.env['res.users'].browse(internal['user_id'])

            agents_with_total_prime.append({
                'user_id': internal['user_id'],
                'user_name': internal['user_name'],
                'total_points': internal['total_points'],
                'details': internal['details'],
                'prime_services': prime_services,
                'prime_speciale': prime_speciale,
                'prime_totale': prime_totale,
                'is_premier_national': False,
                'is_premier_regional': False,
                'zone_ids': user.zone_ids.ids if user.zone_ids else []
            })

        # 4. Trier par prime totale
        agents_with_total_prime.sort(key=lambda x: x['prime_totale'], reverse=True)

        # 5. Chercher les barèmes
        bareme_premier_national = self.search([
            ('name', 'ilike', 'Premier National'),
            ('type', '=', 'coefficient')
        ], limit=1)

        bareme_premier_regional = self.search([
            ('name', 'ilike', 'Premier Régional'),
            ('type', '=', 'coefficient')
        ], limit=1)

        # DEBUG: Vérifier si les barèmes sont trouvés
        print(
            f"DEBUG: Barème Premier National trouvé: {bareme_premier_national.name if bareme_premier_national else 'NON'}")
        print(
            f"DEBUG: Barème Premier Régional trouvé: {bareme_premier_regional.name if bareme_premier_regional else 'NON'}")

        # 6. ATTRIBUER LE PREMIER NATIONAL
        if agents_with_total_prime and bareme_premier_national:
            premier_agent = agents_with_total_prime[0]
            bonus_points = bareme_premier_national.coefficient
            bonus_prime = bonus_points * 100

            # Marquer comme Premier National
            premier_agent['is_premier_national'] = True

            # Ajouter le bonus dans les détails
            premier_agent['details']['premier_national'] = {
                'count': 1,
                'coefficient': bareme_premier_national.coefficient,
                'points': bonus_points,
                'bareme_name': 'Premier National 🏆'
            }

            # Ajouter au total des points ET de la prime
            premier_agent['total_points'] += bonus_points
            premier_agent['prime_totale'] += bonus_prime

            print(f"🏆 PREMIER NATIONAL: {premier_agent['user_name']} avec {premier_agent['prime_totale']} DA")

        # 7. ATTRIBUER LES PREMIERS RÉGIONAUX (PAR ZONE)
        if bareme_premier_regional:
            # Créer un dictionnaire pour suivre le meilleur agent par zone
            meilleurs_par_zone = {}

            for agent in agents_with_total_prime:
                for zone_id in agent['zone_ids']:
                    # Si cette zone n'a pas encore de meilleur agent, OU si cet agent a une meilleure prime
                    if zone_id not in meilleurs_par_zone or agent['prime_totale'] > meilleurs_par_zone[zone_id][
                        'prime_totale']:
                        meilleurs_par_zone[zone_id] = agent

            # Appliquer le bonus Premier Régional aux agents sélectionnés
            for zone_id, agent in meilleurs_par_zone.items():
                # SUPPRIMER LA CONDITION 'not agent['is_premier_national']'
                # pour permettre la double distinction
                agent['is_premier_regional'] = True
                bonus_points_regional = bareme_premier_regional.coefficient
                bonus_prime_regional = bonus_points_regional * 100

                # Ajouter le bonus dans les détails
                if 'premier_regional' not in agent['details']:
                    agent['details']['premier_regional'] = {
                        'count': 0,
                        'coefficient': bareme_premier_regional.coefficient,
                        'points': 0,
                        'bareme_name': 'Premier Régional 🥈'
                    }

                agent['details']['premier_regional']['count'] += 1
                agent['details']['premier_regional']['points'] += bonus_points_regional

                # Récupérer le nom de la zone
                zone = self.env['zone'].browse(zone_id)
                print(f"🥈 PREMIER RÉGIONAL (Zone {zone.name if zone else zone_id}): {agent['user_name']}")

        # DEBUG: Afficher les agents avec Premier Régional
        premiers_regionaux = [agent for agent in agents_with_total_prime if agent.get('is_premier_regional')]
        print(f"DEBUG: Agents Premier Régional: {[agent['user_name'] for agent in premiers_regionaux]}")

        # 8. Mettre à jour internal_results AVEC TOUS les agents
        for agent in agents_with_total_prime:
            # Trouver l'agent correspondant dans internal_results
            for internal in internal_results:
                if internal['user_id'] == agent['user_id']:
                    # Mettre à jour les champs
                    internal.update({
                        'is_premier_national': agent['is_premier_national'],
                        'is_premier_regional': agent['is_premier_regional'],
                        'total_points': agent['total_points'],
                        'prime_totale': agent['prime_totale']
                    })

                    # Ajouter les détails des bonus SI ils existent
                    if agent.get('is_premier_national') and 'premier_national' in agent['details']:
                        internal['details']['premier_national'] = agent['details']['premier_national']

                    if agent.get('is_premier_regional') and 'premier_regional' in agent['details']:
                        internal['details']['premier_regional'] = agent['details']['premier_regional']

                    break  # Sortir de la boucle interne une fois trouvé

        # 9. Afficher un résumé pour débogage
        print("\n" + "=" * 50)
        print("RÉSUMÉ DES PREMIERS RÉGIONAUX:")
        for agent in agents_with_total_prime:
            if agent.get('is_premier_regional'):
                print(f"✓ {agent['user_name']} - Premier Régional")
        print("=" * 50 + "\n")

        return internal_results