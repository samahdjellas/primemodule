from odoo import models, fields, api
from datetime import datetime, date
import calendar
import math


class BaremePrime(models.Model):
    _name = 'bareme.prime'
    _description = 'Barème de Prime'

    name = fields.Char(string='Nom', required=True)
    zone_id = fields.Many2one('zone', string='Zone', required=True)
    type = fields.Selection([
        ('pourcentage', 'Pourcentage'),
        ('coefficient', 'coefficient'),
    ], string='Type de prime', required=True, default='pourcentage')
    valeur_pourcentage = fields.Integer(string='Valeur (%)')
    coefficient = fields.Integer(string='coefficient')

    stat_type = fields.Selection([
        ('lavage', 'Lavage'),
        ('livraison', 'Livraison'),
        ('maintenance', 'Maintenance'),
        ('degradation', 'Dégradation'),
        ('option', 'Option'),
        ('premier', 'Premier'),
    ], string='Type de statistique', help="Permet de catégoriser les barèmes")

    def _ceil(self, value):
        """Arrondit toujours au supérieur (ex: 1.27 → 2, 589652.3 → 589653)"""
        return math.ceil(value) if value else 0

    def _normalize_year_month(self, year, month):
        """
        Normalise year et month.
        Si l'une des valeurs est invalide ou manquante,
        on retourne l'année ET le mois ACTUELS.
        """
        now = datetime.now()
        current_year = now.year
        current_month = now.month

        y = None
        if year is not None and year not in (False, '', 'null', 'undefined'):
            try:
                y = int(year)
                if not (2000 <= y <= 2100):
                    y = None
            except (ValueError, TypeError):
                y = None

        m = None
        if month is not None and month not in (False, '', 'null', 'undefined'):
            try:
                m = int(month)
                if not (1 <= m <= 12):
                    m = None
            except (ValueError, TypeError):
                m = None

        if y is None or m is None:
            print(
                f"  [normalize] year={year!r} ou month={month!r} invalide → utilisation de {current_month}/{current_year}")
            y = current_year
            m = current_month
        else:
            print(f"  [normalize] year={y}, month={m} ✅")

        return y, m

    # ========== MÉTHODES POUR FILTRAGE MOIS ==========

    def _get_taux_change_eur_dzd(self):
        """
        Récupère le taux de change EUR → DZD
        depuis le modèle taux.change (primaire=1 EUR = montant DZD)
        """
        taux_record = self.env['taux.change'].search([], limit=1, order='id desc')
        if taux_record and taux_record.montant > 0:
            print(f"✅ Taux EUR/DZD trouvé: 1 EUR = {taux_record.montant} DZD")
            return taux_record.montant
        print("⚠️ Taux EUR/DZD non trouvé, utilisation de 1.0 par défaut")
        return 1.0

    def _get_date_range_for_month(self, year, month):
        first_day = datetime(year, month, 1, 0, 0, 0)
        last_day_of_month = calendar.monthrange(year, month)[1]
        last_day = datetime(year, month, last_day_of_month, 23, 59, 59)
        return first_day, last_day

    def _apply_month_filter_to_domain(self, domain, model_name, year=None, month=None):
        """
        FIX PRINCIPAL : utilise des objets date/datetime natifs Python
        pour éviter tout problème de format string avec Odoo ORM.
        """
        if not year or not month:
            return domain

        try:
            year = int(year)
            month = int(month)
        except (ValueError, TypeError):
            return domain

        if not (2000 <= year <= 2100) or not (1 <= month <= 12):
            return domain

        domain = list(domain)
        last_day = calendar.monthrange(year, month)[1]

        if model_name == 'livraison':
            # date_de_livraison est un champ Date (pas Datetime)
            date_from = date(year, month, 1)
            date_to = date(year, month, last_day)
            domain.append(('date_de_livraison', '>=', date_from))
            domain.append(('date_de_livraison', '<=', date_to))
            print(f"✅ FILTRE livraison: {date_from} → {date_to}")

        elif model_name == 'depense.record':
            # create_date est un champ Datetime Odoo (stocké UTC)
            date_from = datetime(year, month, 1, 0, 0, 0)
            date_to = datetime(year, month, last_day, 23, 59, 59)
            domain.append(('create_date', '>=', date_from))
            domain.append(('create_date', '<=', date_to))
            print(f"✅ FILTRE depense.record: {date_from} → {date_to}")

        elif model_name == 'maintenance.record':
            # create_date est un champ Datetime Odoo (stocké UTC)
            date_from = datetime(year, month, 1, 0, 0, 0)
            date_to = datetime(year, month, last_day, 23, 59, 59)
            domain.append(('create_date', '>=', date_from))
            domain.append(('create_date', '<=', date_to))
            print(f"✅ FILTRE maintenance.record: {date_from} → {date_to}")

        elif model_name == 'ajouter.point':
            # date est un champ Date simple
            date_from = date(year, month, 1)
            date_to = date(year, month, last_day)
            domain.append(('date', '>=', date_from))
            domain.append(('date', '<=', date_to))
            print(f"✅ FILTRE ajouter.point: {date_from} → {date_to}")

        return domain

    # ========== MÉTHODE PRINCIPALE ==========

    @api.model
    def calculate_agent_points_with_ranking_monthly(self, year=None, month=None):
        self = self.sudo()
        print(f"🟡 RAW ARGS: year={year!r} (type={type(year).__name__}), month={month!r}")

        year, month = self._normalize_year_month(year, month)

        print(f"🔴 PARAMÈTRES UTILISÉS: year={year}, month={month}")
        print(f"\n" + "=" * 80)
        month_name = self._get_month_name(month)
        print(f"CALCUL DES POINTS POUR {month_name} {year}")
        print("=" * 80)

        agent_group = None
        try:
            agent_group = self.env.ref('access_rights_groups.group_agent', raise_if_not_found=False)
        except:
            pass
        if not agent_group:
            agent_group = self.env['res.groups'].search([('name', '=', 'AGENT')], limit=1)
        if not agent_group:
            agent_group = self.env['res.groups'].search([('name', 'ilike', 'agent')], limit=1)

        if not agent_group:
            print("ERREUR: Groupe AGENT non trouvé!")
            return []

        print(f"✅ Groupe trouvé: {agent_group.name}")
        users = self.env['res.users'].search([('groups_id', 'in', [agent_group.id])])

        # ── FILTRER LES AGENTS BLOQUÉS ──
        blocked_ids = self._get_blocked_user_ids(year, month)
        if blocked_ids:
            users = users.filtered(lambda u: u.id not in blocked_ids)
            print(f"🚫 Agents bloqués filtrés, reste {len(users)} agents actifs")

        print(f"Nombre d'agents trouvés: {len(users)}")
        print(f"Agents: {[user.name for user in users]}")

        livraison_domain = [
            ('livrer_par_last', 'in', users.ids),
            ('stage', '=', 'livre')
        ]
        livraison_domain = self._apply_month_filter_to_domain(livraison_domain, 'livraison', year, month)
        all_livraisons = self.env['livraison'].search(livraison_domain)
        print(f"Nombre total de livraisons: {len(all_livraisons)}")

        lavage_type = self.env['type.depens'].search([('name', 'ilike', 'lavage')], limit=1)
        lavage_id = lavage_type.id if lavage_type else 23

        depense_domain = [
            ('caisse.user_id', 'in', users.ids),
            ('type_depense', '=', lavage_id),
            ('status', '=', 'valide')
        ]
        depense_domain = self._apply_month_filter_to_domain(depense_domain, 'depense.record', year, month)
        all_depenses = self.env['depense.record'].search(depense_domain)
        print(f"Nombre total de dépenses lavage: {len(all_depenses)}")

        maintenance_domain = [
            ('create_uid', 'in', users.ids),
            ('type_maintenance_id.id', '!=', 3),
        ]
        maintenance_domain = self._apply_month_filter_to_domain(maintenance_domain, 'maintenance.record', year, month)
        all_maintenances = self.env['maintenance.record'].search(maintenance_domain)
        print(f"Nombre total de maintenances: {len(all_maintenances)}")

        # APRÈS
        degradation_domain = [
            ('livrer_par_last', 'in', users.ids),
            ('lv_type', '=', 'restitution'),
            ('stage', '=', 'livre'),
            ('degradation_limit_da', '>', 0)
        ]
        degradation_domain = self._apply_month_filter_to_domain(degradation_domain, 'livraison', year, month)
        all_degradations = self.env['livraison'].search(degradation_domain)
        print(f"Nombre total de dégradations: {len(all_degradations)}")

        degradations_by_user = {}
        for deg in all_degradations:
            user_id = deg.livrer_par_last.id
            if user_id not in degradations_by_user:
                # APRÈS
                degradations_by_user[user_id] = {
                    'count': 0,
                    'total_amount': 0.0,
                    'total_amount_brut': 0.0,
                    'total_penalit_carburant': 0.0,
                    'total_penalit_klm': 0.0,
                    'items': []
                }
            # APRÈS
            degradations_by_user[user_id]['count'] += 1
            penalit_carburant = deg.penalit_carburant or 0.0
            penalit_klm = deg.penalit_klm_dinar or 0.0
            montant_net = deg.degradation_limit_da - penalit_carburant - penalit_klm
            montant_net = max(montant_net, 0.0)
            degradations_by_user[user_id]['total_amount'] += montant_net
            degradations_by_user[user_id]['total_amount_brut'] += deg.degradation_limit_da
            degradations_by_user[user_id]['total_penalit_carburant'] += penalit_carburant
            degradations_by_user[user_id]['total_penalit_klm'] += penalit_klm
            degradations_by_user[user_id]['items'].append({
                'id': deg.id,
                'amount': montant_net,
                'amount_brut': deg.degradation_limit_da,
                'penalit_carburant': penalit_carburant,
                'penalit_klm': penalit_klm,
                'date': deg.date_de_livraison,
                'vehicule': deg.vehicule.name if deg.vehicule else 'N/A'
            })
            print(
                f"  Dégradation {deg.id}: brut={deg.degradation_limit_da} - carburant={penalit_carburant} - klm={penalit_klm} = net={montant_net}")

        internal_results = []

        depenses_by_user = {}
        for dep in all_depenses:
            user_id = dep.caisse.user_id.id
            depenses_by_user[user_id] = depenses_by_user.get(user_id, 0) + 1

        livraisons_by_user = {}
        for lv in all_livraisons:
            if lv.livrer_par_last.id not in livraisons_by_user:
                livraisons_by_user[lv.livrer_par_last.id] = []
            livraisons_by_user[lv.livrer_par_last.id].append(lv)

        maintenances_by_user = {}
        for maint in all_maintenances:
            if maint.create_uid.id not in maintenances_by_user:
                maintenances_by_user[maint.create_uid.id] = {'with_alert': 0, 'without_alert': 0}
            if maint.alert_id:
                maintenances_by_user[maint.create_uid.id]['with_alert'] += 1
            else:
                maintenances_by_user[maint.create_uid.id]['without_alert'] += 1

        for user in users:
            print("\n" + "-" * 80)
            print(f"TRAITEMENT DE L'AGENT: {user.name} (ID: {user.id})")
            print("-" * 80)

            total_points = 0
            total_prime_pourcentage = 0.0
            details = {}
            agent_zones = user.zone_ids
            agent_zone_ids = agent_zones.ids
            print(f"Zones de l'agent: {[zone.name for zone in agent_zones]}")

            # ── LAVAGE ──
            lavage_count = depenses_by_user.get(user.id, 0)
            print(f"Nombre de lavages: {lavage_count}")
            if lavage_count > 0:
                bareme = self._get_bareme_for_zone_and_type('lavage', None, agent_zone_ids)
                if bareme:
                    points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(lavage_count, bareme,
                                                                                            'lavage')
                    if bareme_type == 'pourcentage':
                        total_prime_pourcentage += points
                        details['lavage'] = {
                            'count': lavage_count, 'coefficient': coefficient, 'points': points,
                            'prime_da': points, 'total_amount': 0.0, 'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }
                    else:
                        total_points += points
                        details['lavage'] = {
                            'count': lavage_count, 'coefficient': coefficient, 'points': points,
                            'prime_da': 0.0, 'total_amount': 0.0, 'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }

            # ── LIVRAISONS ──
            user_livraisons = livraisons_by_user.get(user.id, [])
            print(f"Nombre total de livraisons pour cet agent: {len(user_livraisons)}")

            livraisons_par_zone = {}
            options_par_zone = {}
            options_totals_par_zone = {}

            for lv in user_livraisons:
                livraison_zone_id = None
                if lv.lv_type == 'livraison' and lv.lieu_depart and lv.lieu_depart.zone:
                    livraison_zone_id = lv.lieu_depart.zone.id
                elif lv.lv_type == 'restitution' and lv.lieu_retour and lv.lieu_retour.zone:
                    livraison_zone_id = lv.lieu_retour.zone.id

                if livraison_zone_id:
                    if livraison_zone_id not in livraisons_par_zone:
                        livraisons_par_zone[livraison_zone_id] = {
                            'normal': 0, 'hors_zone': 0, 'tardive': 0,
                            'hors_zone_tardive': 0, 'hors_ville': 0
                        }
                    if livraison_zone_id not in options_par_zone:
                        options_par_zone[livraison_zone_id] = {
                            'siege_bebe': 0, 'conducteur': 0, 'carburant': 0,
                            'protection_standard': 0, 'protection_max': 0, 'klm_illimite': 0
                        }

                    if livraison_zone_id not in options_totals_par_zone:
                        options_totals_par_zone[livraison_zone_id] = {
                            'conducteur': 0.0, 'carburant': 0.0,
                            'protection_standard': 0.0, 'protection_max': 0.0,
                            'klm_illimite': 0.0,
                            'siege_bebe': 0.0  # ← AJOUT
                        }

                is_tardif = False
                is_hors_zone = False
                if lv.date_de_livraison:
                    heure = lv.date_de_livraison.hour if hasattr(lv.date_de_livraison, 'hour') else 0
                    is_tardif = heure >= 19 or heure < 7
                if livraison_zone_id:
                    zone_obj = self.env['zone'].browse(livraison_zone_id)
                    is_hors_zone = zone_obj not in agent_zones

                city_depart = None
                city_retour = None
                if lv.lv_type == 'livraison':
                    if lv.lieu_depart and lv.lieu_depart.city:
                        city_depart = lv.lieu_depart.city.id
                    if lv.lieu_retour and lv.lieu_retour.city:
                        city_retour = lv.lieu_retour.city.id
                elif lv.lv_type == 'restitution':
                    if lv.lieu_retour and lv.lieu_retour.city:
                        city_depart = lv.lieu_retour.city.id
                    if lv.lieu_depart and lv.lieu_depart.city:
                        city_retour = lv.lieu_depart.city.id

                # Vérifier si l'agent a une zone dont le nom = 'EST'
                agent_zones_obj = self.env['zone'].browse(agent_zone_ids)
                agent_in_est = any(z.name == 'EST' for z in agent_zones_obj)

                is_hors_ville = (
                        (agent_in_est
                         and lv.lieu_depart and lv.lieu_retour
                         and livraison_zone_id is not None
                         and not is_hors_zone
                         and lv.lv_type == 'livraison'
                         and lv.lieu_depart.id != 4) or
                        (agent_in_est
                         and lv.lieu_depart and lv.lieu_retour
                         and livraison_zone_id is not None
                         and not is_hors_zone
                         and lv.lv_type == 'restitution'
                                           ''
                         and lv.lieu_depart.id != 4)
                )

                if livraison_zone_id:
                    if is_tardif and is_hors_zone:
                        livraisons_par_zone[livraison_zone_id]['hors_zone_tardive'] += 1
                    elif is_tardif and is_hors_ville:
                        # tardive + hors ville → on comptabilise les deux !
                        livraisons_par_zone[livraison_zone_id]['tardive'] += 1
                        livraisons_par_zone[livraison_zone_id]['hors_ville'] += 1
                    elif is_tardif:
                        livraisons_par_zone[livraison_zone_id]['tardive'] += 1
                    elif is_hors_zone:
                        livraisons_par_zone[livraison_zone_id]['hors_zone'] += 1
                    elif is_hors_ville:
                        livraisons_par_zone[livraison_zone_id]['hors_ville'] += 1
                    else:
                        livraisons_par_zone[livraison_zone_id]['normal'] += 1

                    if lv.lv_type == 'livraison':

                        # Récupérer les totaux depuis la réservation si elle existe
                        res = lv.reservation if lv.reservation else None

                        if lv.sb_ajout:
                            options_par_zone[livraison_zone_id]['siege_bebe'] += 1
                            val = (res.opt_siege_a_total if res and res.opt_siege_a_total else lv.sb_total) or 0
                            options_totals_par_zone[livraison_zone_id]['siege_bebe'] += val

                        if lv.nd_driver_ajoute:
                            options_par_zone[livraison_zone_id]['conducteur'] += 1
                            val = (
                                      res.opt_nd_driver_total if res and res.opt_nd_driver_total else lv.nd_driver_total) or 0
                            options_totals_par_zone[livraison_zone_id]['conducteur'] += val

                        if lv.carburant_ajoute:
                            options_par_zone[livraison_zone_id]['carburant'] += 1
                            # carburant : pas de champ reservation mentionné → on garde lv.carburant_total_f
                            val = lv.carburant_total_f or 0
                            options_totals_par_zone[livraison_zone_id]['carburant'] += val

                        if lv.standart_ajoute:
                            options_par_zone[livraison_zone_id]['protection_standard'] += 1
                            val = (
                                      res.opt_protection_total if res and res.opt_protection_total else lv.standart_total) or 0
                            options_totals_par_zone[livraison_zone_id]['protection_standard'] += val

                        if lv.max_ajoute:
                            options_par_zone[livraison_zone_id]['protection_max'] += 1
                            val = (res.opt_protection_total if res and res.opt_protection_total else lv.max_total) or 0
                            options_totals_par_zone[livraison_zone_id]['protection_max'] += val

                        if lv.klm_ajoute:
                            options_par_zone[livraison_zone_id]['klm_illimite'] += 1
                            val = (res.opt_klm_total if res and res.opt_klm_total else lv.klm_total) or 0
                            options_totals_par_zone[livraison_zone_id]['klm_illimite'] += val

            print("\nTRAITEMENT DES LIVRAISONS:")
            for stat_key, zone_data_key in [
                ('livraison_normal', 'normal'),
                ('livraison_hors_zone', 'hors_zone'),
                ('livraison_tardive', 'tardive'),
                ('livraison_hors_zone_tardive', 'hors_zone_tardive'),
                ('livraison_hors_ville', 'hors_ville'),
            ]:
                total_count = 0
                total_points_for_type = 0
                total_prime_da_for_type = 0.0

                for zone_id, counts in livraisons_par_zone.items():
                    count = counts.get(zone_data_key, 0)
                    if count > 0:
                        zone_name = self.env['zone'].browse(zone_id).name if zone_id else 'N/A'
                        print(f"  {stat_key} - Zone {zone_name}: {count} livraisons")
                        bareme = self._get_bareme_for_zone_and_type(stat_key, zone_id, agent_zone_ids)
                        if bareme:
                            points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                                count, bareme, stat_key)
                            print(f"    Barème: {bareme.name}, type={bareme_type}, points={points}")
                            if bareme_type == 'pourcentage':
                                total_prime_pourcentage += points
                                total_prime_da_for_type += points
                            else:
                                total_points += points
                                total_points_for_type += points
                            total_count += count

                if total_count > 0:
                    bareme_global = self._get_bareme_for_zone_and_type(stat_key, None, agent_zone_ids)
                    if bareme_global:
                        details[stat_key] = {
                            'count': total_count,
                            'coefficient': bareme_global.coefficient if bareme_global.type == 'coefficient' else bareme_global.valeur_pourcentage,
                            'points': total_points_for_type if bareme_global.type == 'coefficient' else 0,
                            'prime_da': total_prime_da_for_type if bareme_global.type == 'pourcentage' else 0.0,
                            'total_amount': 0.0,
                            'bareme_name': bareme_global.name,
                            'zone_name': bareme_global.zone_id.name if bareme_global.zone_id else 'Global',
                            'type': bareme_global.type,
                        }

            print("\nTRAITEMENT DES OPTIONS:")
            for stat_key in ['siege_bebe', 'conducteur', 'carburant', 'protection_standard',
                             'protection_max', 'klm_illimite']:
                total_count = 0
                total_points_for_option = 0
                total_prime_da_for_option = 0.0
                total_amount_for_option = 0.0

                # APRÈS
                total_amount_dzd_for_option = 0.0

                for zone_id, options in options_par_zone.items():
                    count = options.get(stat_key, 0)
                    if count > 0:
                        zone_total_amount = 0.0
                        if stat_key in self.STAT_KEYS_WITH_TOTAL_FIELD:
                            zone_total_amount = options_totals_par_zone.get(zone_id, {}).get(stat_key, 0.0)
                            total_amount_for_option += zone_total_amount

                            # Calcul du montant DZD pour affichage
                            if stat_key in self.STAT_KEYS_IN_EURO and zone_total_amount > 0:
                                taux = self._get_taux_change_eur_dzd()
                                total_amount_dzd_for_option += zone_total_amount * taux
                            else:
                                total_amount_dzd_for_option += zone_total_amount

                        bareme = self._get_bareme_for_zone_and_type(stat_key, zone_id, agent_zone_ids)
                        if bareme:
                            points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                                count, bareme, stat_key, total_amount=zone_total_amount)
                            if bareme_type == 'pourcentage':
                                total_prime_pourcentage += points
                                total_prime_da_for_option += points
                            else:
                                total_points += points
                                total_points_for_option += points
                            total_count += count

                if total_count > 0 or stat_key == 'carburant':
                    bareme_global = self._get_bareme_for_zone_and_type(stat_key, None, agent_zone_ids)
                    if bareme_global:
                        details[stat_key] = {
                            'count': total_count,
                            'coefficient': bareme_global.coefficient if bareme_global.type == 'coefficient' else bareme_global.valeur_pourcentage,
                            'points': total_points_for_option if bareme_global.type == 'coefficient' else 0,
                            'prime_da': total_prime_da_for_option if bareme_global.type == 'pourcentage' else 0.0,
                            'total_amount': total_amount_for_option,
                            'total_amount_dzd': total_amount_dzd_for_option,
                            'bareme_name': bareme_global.name,
                            'zone_name': bareme_global.zone_id.name if bareme_global.zone_id else 'Global',
                            'type': bareme_global.type,
                        }

            # ── MAINTENANCE ──
            user_maint = maintenances_by_user.get(user.id, {'with_alert': 0, 'without_alert': 0})
            print(f"\nMAINTENANCES: avec alerte={user_maint['with_alert']}, "
                  f"sans alerte={user_maint['without_alert']}")

            if user_maint['without_alert'] > 0:
                bareme = self._get_bareme_for_zone_and_type('maintenance', None, agent_zone_ids)
                if bareme:
                    points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                        user_maint['without_alert'], bareme, 'maintenance')
                    if bareme_type == 'pourcentage':
                        total_prime_pourcentage += points
                        details['maintenance'] = {
                            'count': user_maint['without_alert'], 'coefficient': coefficient,
                            'points': points, 'prime_da': points, 'total_amount': 0.0,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }
                    else:
                        total_points += points
                        details['maintenance'] = {
                            'count': user_maint['without_alert'], 'coefficient': coefficient,
                            'points': points, 'prime_da': 0.0, 'total_amount': 0.0,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }

            # ── ALERTES ──
            if user_maint['with_alert'] > 0:
                bareme = self._get_bareme_for_zone_and_type('alerte', None, agent_zone_ids)
                if bareme:
                    points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                        user_maint['with_alert'], bareme, 'alerte')
                    if bareme_type == 'pourcentage':
                        total_prime_pourcentage += points
                        details['alerte'] = {
                            'count': user_maint['with_alert'], 'coefficient': coefficient,
                            'points': points, 'prime_da': points, 'total_amount': 0.0,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }
                    else:
                        total_points += points
                        details['alerte'] = {
                            'count': user_maint['with_alert'], 'coefficient': coefficient,
                            'points': points, 'prime_da': 0.0, 'total_amount': 0.0,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }

            # ── DÉGRADATIONS ──
            user_degradations = degradations_by_user.get(user.id, {'count': 0, 'total_amount': 0.0})
            print(f"\nDÉGRADATIONS: count={user_degradations['count']}, "
                  f"total_amount={user_degradations['total_amount']}")

            # APRÈS
            if user_degradations['total_amount'] > 0:
                bareme = self._get_bareme_for_zone_and_type('degradation', None, agent_zone_ids)
                if bareme:
                    if bareme.type == 'pourcentage':
                        points, coefficient, bareme_type, _ = self._calculate_degradation_points(
                            user_degradations['total_amount'], bareme, 'degradation')
                        total_prime_pourcentage += points
                        details['degradation'] = {
                            'count': user_degradations['count'],
                            'total_amount': user_degradations['total_amount'],
                            'total_amount_brut': user_degradations['total_amount_brut'],
                            'total_penalit_carburant': user_degradations['total_penalit_carburant'],
                            'total_penalit_klm': user_degradations['total_penalit_klm'],
                            'coefficient': coefficient, 'points': points, 'prime_da': points,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }
                    else:
                        points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                            user_degradations['count'], bareme, 'degradation')
                        total_points += points
                        details['degradation'] = {
                            'count': user_degradations['count'],
                            'total_amount': user_degradations['total_amount'],
                            'total_amount_brut': user_degradations['total_amount_brut'],
                            'total_penalit_carburant': user_degradations['total_penalit_carburant'],
                            'total_penalit_klm': user_degradations['total_penalit_klm'],
                            'coefficient': coefficient, 'points': points, 'prime_da': 0.0,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme_type
                        }

            # ── REMPLIR LES DÉTAILS MANQUANTS ──
            for stat_key in [
                'lavage', 'livraison_normal', 'livraison_hors_zone', 'livraison_tardive',
                'livraison_hors_zone_tardive', 'livraison_hors_ville', 'maintenance', 'alerte',
                'siege_bebe', 'conducteur', 'carburant', 'protection_standard',
                'protection_max', 'klm_illimite', 'degradation',
            ]:
                if stat_key not in details:
                    bareme = self._get_bareme_for_zone_and_type(stat_key, None, agent_zone_ids)
                    if bareme:
                        coefficient = bareme.coefficient if bareme.type == 'coefficient' else bareme.valeur_pourcentage
                        details[stat_key] = {
                            'count': 0, 'coefficient': coefficient, 'points': 0,
                            'prime_da': 0.0, 'total_amount': 0.0,
                            'bareme_name': bareme.name,
                            'zone_name': bareme.zone_id.name if bareme.zone_id else 'Global',
                            'type': bareme.type
                        }

            prime_points = self._ceil(total_points * 100)
            prime_pourcentage = self._ceil(total_prime_pourcentage)
            prime_services = prime_points + prime_pourcentage

            print(f"\nRÉSUMÉ POUR {user.name}:")
            print(f"  Total points: {total_points}")
            print(f"  Prime points: {prime_points}")
            print(f"  Prime pourcentage: {prime_pourcentage}")
            print(f"  Prime services: {prime_services}")

            internal_results.append({
                'user_id': user.id,
                'user_name': user.name,
                'total_points': total_points,
                'total_prime_pourcentage': total_prime_pourcentage,
                'prime_points': prime_points,
                'prime_pourcentage': prime_pourcentage,
                'prime_services': prime_services,
                'details': details,
                'is_premier_national': False,
                'is_premier_regional': False,
                'zone_ids': agent_zone_ids,
                'period': f"{month}/{year}"
            })

        # ── CLASSEMENT + PRIMES MANUELLES ──
        manual_results = self.calculate_manual_points_prime_monthly(year, month)

        agents_with_total_prime = []
        for internal in internal_results:
            manual = next((m for m in manual_results if m['user_id'] == internal['user_id']), None)
            prime_services = internal['prime_services']
            # total_prime est en points bruts → convertir en DA (×100) puis ceil
            prime_speciale_da = math.ceil(manual['total_prime'] * 100) if manual else 0

            prime_finale = prime_services + prime_speciale_da

            # Score classement = prime finale réelle en DA (services + divers convertis)
            score_classement = prime_finale

            user = self.env['res.users'].browse(internal['user_id'])



            agents_with_total_prime.append({
                'user_id': internal['user_id'],
                'user_name': internal['user_name'],
                'total_points': internal['total_points'],
                'total_prime_pourcentage': internal['total_prime_pourcentage'],
                'prime_points': internal['prime_points'],
                'prime_pourcentage': internal['prime_pourcentage'],
                'prime_services': prime_services,
                'prime_speciale': prime_speciale_da,
                'details': internal['details'],
                'is_premier_national': False,
                'is_premier_regional': False,
                'zone_ids': user.zone_ids.ids if user.zone_ids else [],
                'period': internal['period'],
                'prime_totale': prime_finale,
                'score_classement': score_classement,  # ✅ NOUVEAU
            })

        # ── TRI par score_classement AVANT attribution des bonus ──
        agents_with_total_prime.sort(key=lambda x: x['score_classement'], reverse=True)

        print("\nCLASSEMENT BRUT AVANT BONUS (basé sur points internes + points divers):")
        for i, a in enumerate(agents_with_total_prime, 1):
            print(f"  {i}. {a['user_name']}: score={a['score_classement']} pts "
                  f"(internes={a['total_points']} + divers={a['score_classement'] - a['total_points']:.2f}) "
                  f"| prime_finale={a['prime_totale']} DA")

        # ── Sauvegarder score_classement AVANT bonus pour le calcul régional ──
        score_classement_original = {a['user_id']: a['score_classement'] for a in agents_with_total_prime}

        # ── BONUS PREMIER NATIONAL (= 1er sur score_classement) ──
        bareme_premier_national = self._get_bareme_for_zone_and_type('premier_national', None, [])
        if agents_with_total_prime and bareme_premier_national:
            premier_national = agents_with_total_prime[0]  # ✅ 1er sur score_classement
            points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                1, bareme_premier_national, 'premier_national')
            bonus_national = self._ceil(points * 100 if bareme_type == 'coefficient' else points)

            print(f"\n🏆 PREMIER NATIONAL: {premier_national['user_name']} "
                  f"(score={premier_national['score_classement']} pts) → bonus +{bonus_national} DA")

            premier_national['is_premier_national'] = True
            premier_national['details']['premier_national'] = {
                'count': 1, 'coefficient': coefficient, 'points': points,
                'prime_da': bonus_national, 'total_amount': 0.0,
                'bareme_name': 'Premier National', 'zone_name': 'Global', 'type': bareme_type,
            }
            if bareme_type == 'coefficient':
                premier_national['total_points'] += points
                premier_national['prime_points'] += points * 100
            else:
                premier_national['total_prime_pourcentage'] += bonus_national
                premier_national['prime_pourcentage'] += bonus_national
            premier_national['prime_services'] += bonus_national
            premier_national['prime_totale'] += bonus_national
            # ✅ Mettre à jour aussi le score après bonus
            premier_national['score_classement'] += (points if bareme_type == 'coefficient' else bonus_national / 100.0)

        # ── BONUS PREMIER RÉGIONAL (= 1er par zone sur score_classement original) ──
        bareme_premier_regional = self._get_bareme_for_zone_and_type('premier_regional', None, [])
        if bareme_premier_regional:
            # Zones occupées par le premier national → pas de premier régional dedans
            zones_du_national = set()
            for agent in agents_with_total_prime:
                if agent['is_premier_national']:
                    zones_du_national.update(agent['zone_ids'])

            meilleurs_par_zone = {}
            for agent in agents_with_total_prime:
                if agent['is_premier_national']:
                    continue
                for zone_id in agent['zone_ids']:
                    if zone_id in zones_du_national:  # ← zone du national : on skip
                        continue
                    sc = score_classement_original[agent['user_id']]
                    if zone_id not in meilleurs_par_zone or \
                            sc > score_classement_original[meilleurs_par_zone[zone_id]['user_id']]:
                        meilleurs_par_zone[zone_id] = agent

            agents_regionaux_traites = set()
            for zone_id, agent in meilleurs_par_zone.items():
                if agent['user_id'] in agents_regionaux_traites:
                    continue
                agents_regionaux_traites.add(agent['user_id'])

                zone_name = self.env['zone'].browse(zone_id).name if zone_id else 'Inconnue'
                points, coefficient, bareme_type, _ = self._calculate_points_for_bareme(
                    1, bareme_premier_regional, 'premier_regional')
                bonus_regional = self._ceil(points * 100 if bareme_type == 'coefficient' else points)

                print(f"\n🥈 PREMIER RÉGIONAL Zone [{zone_name}]: {agent['user_name']} "
                      f"(score={score_classement_original[agent['user_id']]} pts) "
                      f"→ bonus +{bonus_regional} DA")

                agent['is_premier_regional'] = True
                if 'premier_regional' not in agent['details']:
                    agent['details']['premier_regional'] = {
                        'count': 0, 'coefficient': coefficient, 'points': 0,
                        'prime_da': 0.0, 'total_amount': 0.0,
                        'bareme_name': 'Premier Régional', 'zone_name': zone_name, 'type': bareme_type,
                    }
                agent['details']['premier_regional']['count'] += 1
                agent['details']['premier_regional']['points'] += points
                agent['details']['premier_regional']['prime_da'] += bonus_regional

                if bareme_type == 'coefficient':
                    agent['total_points'] += points
                    agent['prime_points'] += points * 100
                else:
                    agent['total_prime_pourcentage'] += bonus_regional
                    agent['prime_pourcentage'] += bonus_regional
                agent['prime_services'] += bonus_regional
                agent['prime_totale'] += bonus_regional

        # ── TRI FINAL par prime_totale (montant DA, après bonus) ──
        # APRÈS
        for a in agents_with_total_prime:
            manual = next((m for m in manual_results if m['user_id'] == a['user_id']), None)
            prime_speciale_da = math.ceil(manual['total_prime'] * 100) if manual else 0
            a['prime_finale_display'] = a['prime_services'] + prime_speciale_da

        agents_with_total_prime.sort(key=lambda x: x['prime_finale_display'], reverse=True)

        print("\nCLASSEMENT FINAL (prime finale incluant bonus):")
        for i, a in enumerate(agents_with_total_prime, 1):
            print(f"  {i}. {a['user_name']}: {a['prime_totale']} DA "
                  f"({'🏆 National' if a['is_premier_national'] else '🥈 Régional' if a['is_premier_regional'] else '-'})")

        # ── Sync internal_results ──
        for agent in agents_with_total_prime:
            for internal in internal_results:
                if internal['user_id'] == agent['user_id']:
                    internal.update({
                        'is_premier_national': agent['is_premier_national'],
                        'is_premier_regional': agent['is_premier_regional'],
                        'total_points': agent['total_points'],
                        'total_prime_pourcentage': agent['total_prime_pourcentage'],
                        'prime_points': agent['prime_points'],
                        'prime_pourcentage': agent['prime_pourcentage'],
                        'prime_services': agent['prime_services'],
                        'prime_totale': agent['prime_totale'],
                    })
                    if agent.get('is_premier_national') and 'premier_national' in agent['details']:
                        internal['details']['premier_national'] = agent['details']['premier_national']
                    if agent.get('is_premier_regional') and 'premier_regional' in agent['details']:
                        internal['details']['premier_regional'] = agent['details']['premier_regional']
                    break

        print("\n" + "=" * 80)
        print("FIN DU CALCUL MENSUEL")
        print("=" * 80)

        return internal_results

    @api.model
    def calculate_manual_points_prime_monthly(self, year=None, month=None):
        print(f"🟡 MANUEL RAW ARGS: year={year!r} (type={type(year).__name__}), month={month!r}")

        year, month = self._normalize_year_month(year, month)

        print(f"🔴 MANUEL PARAMÈTRES UTILISÉS: year={year}, month={month}")

        agent_group = None
        try:
            agent_group = self.env.ref('access_rights_groups.group_agent', raise_if_not_found=False)
        except:
            pass
        if not agent_group:
            agent_group = self.env['res.groups'].search([('name', '=', 'AGENT')], limit=1)
        if not agent_group:
            agent_group = self.env['res.groups'].search([('name', 'ilike', 'agent')], limit=1)

        if agent_group:
            users = self.env['res.users'].search([('groups_id', 'in', [agent_group.id])])
        else:
            users = self.env['res.users'].search([])

        # ── FILTRER LES AGENTS BLOQUÉS ──
        blocked_ids = self._get_blocked_user_ids(year, month)
        if blocked_ids:
            users = users.filtered(lambda u: u.id not in blocked_ids)
            print(f"🚫 Agents bloqués filtrés (manuel), reste {len(users)} agents actifs")

        # Filtre mois sur ajouter.point (champ date simple)
        domain = [('user_id', 'in', users.ids)]
        domain = self._apply_month_filter_to_domain(domain, 'ajouter.point', year, month)
        all_points_ajoutes = self.env['ajouter.point'].search(domain)

        print(f"Points manuels trouvés (filtre {month}/{year}): {len(all_points_ajoutes)}")

        baremes = self.search([('type', '=', 'coefficient')])
        baremes_by_name_zone = {}
        for bareme in baremes:
            key = (bareme.name, bareme.zone_id.id if bareme.zone_id else False)
            baremes_by_name_zone[key] = bareme

        points_by_user = {}
        for point in all_points_ajoutes:
            user_id = point.user_id.id
            if user_id not in points_by_user:
                points_by_user[user_id] = []
            points_by_user[user_id].append(point)

        results = []
        for user in users:
            total_prime = 0
            details = {}
            agent_zones = user.zone_ids
            user_points = points_by_user.get(user.id, [])

            for point in user_points:
                bareme = None
                for zone in agent_zones:
                    key = (point.type_id.name, zone.id)
                    if key in baremes_by_name_zone:
                        bareme = baremes_by_name_zone[key]
                        break
                if not bareme:
                    key = (point.type_id.name, False)
                    bareme = baremes_by_name_zone.get(key)

                if bareme:
                    prime = point.nombre * bareme.coefficient
                    total_prime += prime
                    type_key = point.type_id.name.lower().replace(' ', '_')
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

            results.append({
                'user_id': user.id,
                'user_name': user.name,
                'total_prime': total_prime,
                'details': details,
                'period': f"{month}/{year}"
            })

        return results

    # ========== MÉTHODES UTILITAIRES ==========

    def _get_month_name(self, month):
        months = ["Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
                  "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"]
        return months[month - 1] if 1 <= month <= 12 else f"Mois {month}"

    def action_calculate_monthly_points(self):
        current_date = datetime.now()
        results = self.calculate_agent_points_with_ranking_monthly(current_date.year, current_date.month)
        month_name = self._get_month_name(current_date.month)
        print(f"\nRÉSULTATS DU MOIS {month_name} {current_date.year}:")
        for result in results:
            print(f"{result['user_name']}: {result.get('prime_totale', 0)} DA")
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {'title': 'Calcul mensuel terminé',
                       'message': f'Calcul effectué pour {month_name} {current_date.year}', 'sticky': False,
                       'type': 'success'}
        }

    def _get_stat_base_value(self, stat_key, count=1):
        return 1 * count

    STAT_KEYS_IN_EURO = {'conducteur', 'protection_standard', 'protection_max', 'siege_bebe', 'klm_illimite'}

    def _calculate_points_for_bareme(self, count, bareme, stat_key, total_amount=0.0):
        if bareme.type == 'coefficient':
            coef = bareme.coefficient or 0
            return count * coef, coef, 'coefficient', 0.0



        # APRÈS

        elif bareme.type == 'pourcentage':

            pct = bareme.valeur_pourcentage or 0

            if stat_key in self.STAT_KEYS_WITH_TOTAL_FIELD and total_amount > 0:

                if stat_key in self.STAT_KEYS_IN_EURO:

                    taux = self._get_taux_change_eur_dzd()

                    total_amount_dzd = total_amount * taux

                    print(f"💱 {stat_key}: {total_amount} EUR × {taux} = {total_amount_dzd} DZD")

                else:

                    total_amount_dzd = total_amount

                points = math.ceil(total_amount_dzd * (pct / 100.0))

            elif stat_key in self.STAT_KEYS_WITH_TOTAL_FIELD and total_amount == 0:

                print(f"⚠️ {stat_key}: total_amount=0, prime=0 (klm_total non renseigné ?)")

                total_amount_dzd = 0.0

                points = 0.0

            else:

                total_amount_dzd = 0.0

                points = count * (pct / 100.0)

            return points, pct, 'pourcentage', total_amount_dzd

    def _calculate_degradation_points(self, amount, bareme, stat_key):
        if bareme.type == 'pourcentage' and bareme.valeur_pourcentage:
            points = amount * (bareme.valeur_pourcentage / 100.0)
            return points, bareme.valeur_pourcentage, 'pourcentage', 0.0

        elif bareme.type == 'coefficient' and bareme.coefficient:
            points = amount / 100 * bareme.coefficient
            return points, bareme.coefficient, 'coefficient', 0.0
        return 0, 0, 'coefficient', 0.0

    def _get_bareme_for_zone_and_type(self, stat_key, zone_id, agent_zone_ids):
        all_baremes = self.search([])
        matching_baremes = []

        for bareme in all_baremes:
            bareme_name = bareme.name.lower()
            is_match = False

            if stat_key == 'lavage' and 'lavage' in bareme_name:
                is_match = True

            elif stat_key == 'livraison_normal' and (
                    'livraison normal' in bareme_name
                    or 'livraison zone' in bareme_name
                    or (
                            ('livraison/restitution' in bareme_name or 'livraison / restitution' in bareme_name)
                            and 'hors zone' not in bareme_name
                            and 'hors_zone' not in bareme_name
                            and 'hors ville' not in bareme_name
                            and 'hors_ville' not in bareme_name
                            and 'tardive' not in bareme_name
                            and 'tardif' not in bareme_name
                    )
            ):
                is_match = True

            elif stat_key == 'livraison_hors_zone' and (
                    ('hors zone' in bareme_name or 'hors_zone' in bareme_name)
                    and 'tardive' not in bareme_name
                    and 'tardif' not in bareme_name
                    and 'hors zone / tardive' not in bareme_name
                    and 'hors zone tardive' not in bareme_name
            ):
                is_match = True

            elif stat_key == 'livraison_tardive' and (
                    ('tardif' in bareme_name or 'tardive' in bareme_name)
                    and 'hors zone' not in bareme_name
                    and 'hors_zone' not in bareme_name
            ):
                is_match = True

            elif stat_key == 'livraison_hors_zone_tardive' and (
                    'hors zone tardive' in bareme_name
                    or 'hors_zone_tardive' in bareme_name
                    or 'hors zone / tardive' in bareme_name
                    or 'livraison / restitution hors zone tardive' in bareme_name
            ):
                is_match = True

            elif stat_key == 'livraison_hors_ville' and (  # ← NOUVEAU
                    'hors ville' in bareme_name
                    or 'hors_ville' in bareme_name
                    or 'inter ville' in bareme_name
                    or 'inter-ville' in bareme_name
            ):
                is_match = True

            elif stat_key == 'maintenance' and 'maintenance' in bareme_name and 'alert' not in bareme_name:
                is_match = True

            elif stat_key == 'alerte' and 'alert' in bareme_name:
                is_match = True

            elif stat_key == 'klm_illimite' and (
                    'klm' in bareme_name
                    or 'kilométrage illimité' in bareme_name
                    or 'kilometrage illimite' in bareme_name
                    or 'illimité' in bareme_name
            ):
                is_match = True

            elif stat_key == 'siege_bebe' and (
                    'siege' in bareme_name or 'bebe' in bareme_name or 'siège' in bareme_name):
                is_match = True

            elif stat_key == 'conducteur' and (
                    '2eme conducteur' in bareme_name
                    or '2ème conducteur' in bareme_name
                    or ('conducteur' in bareme_name and '2' not in bareme_name)
            ):
                is_match = True

            elif stat_key == 'carburant' and 'carburant' in bareme_name:
                is_match = True

            elif stat_key == 'protection_standard' and (
                    'protection standard' in bareme_name
                    or ('standard' in bareme_name and 'protection' in bareme_name)
            ):
                is_match = True

            elif stat_key == 'protection_max' and (
                    'protection max' in bareme_name
                    or ('max' in bareme_name and 'protection' in bareme_name)
            ):
                is_match = True

            elif stat_key == 'premier_national' and 'premier national' in bareme_name:
                is_match = True

            elif stat_key == 'premier_regional' and (
                    'premier régional' in bareme_name
                    or 'premier regional' in bareme_name
            ):
                is_match = True

            elif stat_key == 'degradation' and (
                    'degradation' in bareme_name
                    or 'dégradation' in bareme_name
                    or 'dommage' in bareme_name
            ):
                is_match = True

            if is_match:
                matching_baremes.append(bareme)

        if not matching_baremes:
            return None

        if zone_id and zone_id in agent_zone_ids:
            for bareme in matching_baremes:
                if bareme.zone_id and bareme.zone_id.id == zone_id:
                    return bareme

        for bareme in matching_baremes:
            if bareme.zone_id and bareme.zone_id.id in agent_zone_ids:
                return bareme

        for bareme in matching_baremes:
            if not bareme.zone_id:
                return bareme

        return matching_baremes[0] if matching_baremes else None

    # APRÈS
    STAT_KEYS_IN_EURO = {'conducteur', 'protection_standard', 'protection_max', 'siege_bebe', 'klm_illimite'}

    STAT_KEYS_WITH_TOTAL_FIELD = {
        'conducteur': 'nd_driver_total',
        'carburant': 'carburant_total_f',
        'protection_standard': 'standart_total',
        'protection_max': 'max_total',
        'klm_illimite': 'klm_prix_jours',
        'siege_bebe': 'sb_total',  # ← AJOUT
    }

    # ========== MÉTHODES DE TEST ==========

    def action_test_agents_zones(self):
        self.get_all_agents_with_zones()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test terminé', 'message': 'Vérifiez la console', 'sticky': False, 'type': 'info'}}

    def get_all_agents_with_zones(self):
        users = self.env['res.users'].search([])
        for user in users:
            if user.zone_ids:
                for zone in user.zone_ids:
                    print(f"{{ {user.name} , {zone.name} }}")
            else:
                print(f"{{ {user.name} , Aucune zone }}")

    def get_agents_lavage_count(self):
        users = self.env['res.users'].search([])
        lavage_type = self.env['type.depens'].search([('name', 'ilike', 'lavage')], limit=1)
        lavage_id = lavage_type.id if lavage_type else 23
        all_depenses = self.env['depense.record'].search([
            ('caisse.user_id', 'in', users.ids),
            ('type_depense', '=', lavage_id),
            ('status', '=', 'valide')
        ])
        depenses_by_user = {}
        for depense in all_depenses:
            user_id = depense.caisse.user_id.id
            depenses_by_user[user_id] = depenses_by_user.get(user_id, 0) + 1
        for user in users:
            print(f"{user.name} {{ lavage : {depenses_by_user.get(user.id, 0)} }}")

    def action_test_lavages(self):
        self.get_agents_lavage_count()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test lavages terminé', 'message': 'Vérifiez la console serveur', 'sticky': False,
                           'type': 'info'}}

    def get_agents_livraison_stats(self):
        users = self.env['res.users'].search([])
        all_livraisons = self.env['livraison'].search([('livrer_par_last', 'in', users.ids), ('stage', '=', 'livre')])
        stats_by_user = {user.id: {'normal': 0, 'hors_zone': 0, 'tardif': 0} for user in users}
        for livraison in all_livraisons:
            user_id = livraison.livrer_par_last.id
            if user_id not in stats_by_user:
                continue
            is_tardif = False
            is_hors_zone = False
            if livraison.date_de_livraison:
                heure = livraison.date_de_livraison.hour if hasattr(livraison.date_de_livraison, 'hour') else 0
                is_tardif = heure >= 19 or heure < 7
            user = self.env['res.users'].browse(user_id)
            agent_zones = user.zone_ids
            if livraison.lv_type == 'livraison' and livraison.lieu_depart and livraison.lieu_depart.zone:
                is_hors_zone = livraison.lieu_depart.zone not in agent_zones
            elif livraison.lv_type == 'restitution' and livraison.lieu_retour and livraison.lieu_retour.zone:
                is_hors_zone = livraison.lieu_retour.zone not in agent_zones
            if is_tardif:
                stats_by_user[user_id]['tardif'] += 1
            elif is_hors_zone:
                stats_by_user[user_id]['hors_zone'] += 1
            else:
                stats_by_user[user_id]['normal'] += 1
        for user in users:
            stats = stats_by_user.get(user.id, {'normal': 0, 'hors_zone': 0, 'tardif': 0})
            print(
                f"{user.name} {{ (livraison normal : {stats['normal']}) (livraison hors zone : {stats['hors_zone']}) (livraison tardive : {stats['tardif']}) }}")

    def action_test_livraison_stats(self):
        self.get_agents_livraison_stats()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test statistiques terminé', 'message': 'Vérifiez la console serveur',
                           'sticky': False, 'type': 'info'}}

    def get_agents_degradation_stats(self):
        users = self.env['res.users'].search([])
        retours_degradation = self.env['livraison'].search(
            [('livrer_par_last', 'in', users.ids), ('lv_type', '=', 'restitution'), ('stage', '=', 'livre'),
             ('degradation_limit_da', '>', 0)])
        stats_by_user = {}
        for retour in retours_degradation:
            user_id = retour.livrer_par_last.id
            if user_id not in stats_by_user:
                stats_by_user[user_id] = {'count': 0, 'total_da': 0.0, 'degradations': []}
            stats_by_user[user_id]['count'] += 1
            stats_by_user[user_id]['total_da'] += retour.degradation_limit_da
        for user in users:
            stats = stats_by_user.get(user.id, {'count': 0, 'total_da': 0.0})
            print(f"{user.name} {{ {stats['count']} dégradations , {stats['total_da']:.2f} DA }}")
        return stats_by_user

    def action_test_degradations(self):
        self.get_agents_degradation_stats()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test dégradations terminé', 'message': 'Vérifiez la console serveur',
                           'sticky': False, 'type': 'info'}}

    def get_agents_maintenance_alert_count(self):
        users = self.env['res.users'].search([])
        all_maintenances = self.env['maintenance.record'].search([('create_uid', 'in', users.ids)])
        stats_by_user = {}
        for maint in all_maintenances:
            user_id = maint.create_uid.id
            if user_id not in stats_by_user:
                stats_by_user[user_id] = {'maintenance': 0, 'alert': 0}
            if maint.alert_id:
                stats_by_user[user_id]['alert'] += 1
            else:
                stats_by_user[user_id]['maintenance'] += 1
        for user in users:
            stats = stats_by_user.get(user.id, {'maintenance': 0, 'alert': 0})
            print(f"{user.name} {{ maintenance : {stats['maintenance']} , alert : {stats['alert']} }}")

    def action_test_maintenance_alert(self):
        self.get_agents_maintenance_alert_count()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test maintenances/alertes terminé', 'message': 'Vérifiez la console serveur',
                           'sticky': False, 'type': 'info'}}

    def get_agents_ventes_options(self):
        users = self.env['res.users'].search([])
        livraisons_depart = self.env['livraison'].search(
            [('livrer_par_last', 'in', users.ids), ('lv_type', '=', 'livraison'), ('stage', '=', 'livre')])
        stats_by_user = {}
        for livraison in livraisons_depart:
            user_id = livraison.livrer_par_last.id
            if user_id not in stats_by_user:
                stats_by_user[user_id] = {'siege_bebe': 0, 'nd_driver': 0, 'carburant': 0, 'standart': 0, 'max': 0}
            if livraison.sb_ajout: stats_by_user[user_id]['siege_bebe'] += 1
            if livraison.nd_driver_ajoute: stats_by_user[user_id]['nd_driver'] += 1
            if livraison.carburant_ajoute: stats_by_user[user_id]['carburant'] += 1
            if livraison.standart_ajoute: stats_by_user[user_id]['standart'] += 1
            if livraison.max_ajoute: stats_by_user[user_id]['max'] += 1
        for user in users:
            stats = stats_by_user.get(user.id,
                                      {'siege_bebe': 0, 'nd_driver': 0, 'carburant': 0, 'standart': 0, 'max': 0})
            options_vendues = []
            if stats['siege_bebe'] > 0: options_vendues.append(f"siege bebe : {stats['siege_bebe']}")
            if stats['nd_driver'] > 0: options_vendues.append(f"2eme conducteur : {stats['nd_driver']}")
            if stats['carburant'] > 0: options_vendues.append(f"carburant : {stats['carburant']}")
            if stats['standart'] > 0: options_vendues.append(f"protection standard : {stats['standart']}")
            if stats['max'] > 0: options_vendues.append(f"protection max : {stats['max']}")
            print(f"{user.name} {{ {' , '.join(options_vendues) if options_vendues else 'aucune option vendue'} }}")

    def action_test_ventes_options(self):
        self.get_agents_ventes_options()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Test ventes options terminé', 'message': 'Vérifiez la console serveur',
                           'sticky': False, 'type': 'info'}}

    def calculate_agent_points(self):
        users = self.env['res.users'].search([])
        all_livraisons = self.env['livraison'].search([('livrer_par_last', 'in', users.ids), ('stage', '=', 'livre')])
        all_depenses = self.env['depense.record'].search(
            [('caisse.user_id', 'in', users.ids), ('type_depense', '=', 1), ('status', '=', 'valide')])
        all_maintenances = self.env['maintenance.record'].search([('create_uid', 'in', users.ids)])
        baremes = self.search([('type', '=', 'coefficient')])
        results = []
        depenses_by_user = {}
        for depense in all_depenses:
            user_id = depense.caisse.user_id.id
            depenses_by_user[user_id] = depenses_by_user.get(user_id, 0) + 1
        livraisons_by_user = {}
        for lv in all_livraisons:
            user_id = lv.livrer_par_last.id
            if user_id not in livraisons_by_user:
                livraisons_by_user[user_id] = []
            livraisons_by_user[user_id].append(lv)
        maintenances_by_user = {}
        for maint in all_maintenances:
            user_id = maint.create_uid.id
            if user_id not in maintenances_by_user:
                maintenances_by_user[user_id] = {'with_alert': 0, 'without_alert': 0}
            if maint.alert_id:
                maintenances_by_user[user_id]['with_alert'] += 1
            else:
                maintenances_by_user[user_id]['without_alert'] += 1
        for user in users:
            total_points = 0
            details = {}
            agent_zones = user.zone_ids
            processed_stats = {}
            processed_stats['lavage'] = depenses_by_user.get(user.id, 0)
            user_livraisons = livraisons_by_user.get(user.id, [])
            for key in ['livraison_normal', 'livraison_hors_zone', 'livraison_tardive', 'siege_bebe', 'conducteur',
                        'carburant', 'protection_standard', 'protection_max']:
                processed_stats[key] = 0
            for lv in user_livraisons:
                is_tardif = False
                is_hors_zone = False
                if lv.date_de_livraison:
                    heure = lv.date_de_livraison.hour if hasattr(lv.date_de_livraison, 'hour') else 0
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
                if lv.lv_type == 'livraison':
                    if lv.sb_ajout: processed_stats['siege_bebe'] += 1
                    if lv.nd_driver_ajoute: processed_stats['conducteur'] += 1
                    if lv.carburant_ajoute: processed_stats['carburant'] += 1
                    if lv.standart_ajoute: processed_stats['protection_standard'] += 1
                    if lv.max_ajoute: processed_stats['protection_max'] += 1
            user_maint = maintenances_by_user.get(user.id, {'with_alert': 0, 'without_alert': 0})
            processed_stats['maintenance'] = user_maint['without_alert']
            processed_stats['alerte'] = user_maint['with_alert']
            bareme_mapping = {}
            for bareme in baremes:
                bareme_name = bareme.name.lower()
                stat_key = None
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
                        'conducteur' in bareme_name and '2' not in bareme_name):
                    stat_key = 'conducteur'
                elif 'carburant' in bareme_name:
                    stat_key = 'carburant'
                elif 'protection standard' in bareme_name or (
                        'standard' in bareme_name and 'protection' in bareme_name):
                    stat_key = 'protection_standard'
                elif 'protection max' in bareme_name or ('max' in bareme_name and 'protection' in bareme_name):
                    stat_key = 'protection_max'
                elif 'degradation' in bareme_name or 'dégradation' in bareme_name or 'dommage' in bareme_name:
                    stat_key = 'degradation'
                if stat_key and stat_key not in bareme_mapping:
                    bareme_mapping[stat_key] = bareme
                    count = processed_stats.get(stat_key, 0)
                    if count > 0:
                        points = count * bareme.coefficient
                        total_points += points
                        details[stat_key] = {'count': count, 'coefficient': bareme.coefficient, 'points': points,
                                             'bareme_name': bareme.name}
            results.append(
                {'user_id': user.id, 'user_name': user.name, 'total_points': total_points, 'details': details})
        return results

    def action_calculate_points(self):
        self.calculate_agent_points()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Calcul des points terminé', 'message': 'Vérifiez la console serveur',
                           'sticky': False, 'type': 'success'}}

    def calculate_manual_points_prime(self):
        users = self.env['res.users'].search([])
        all_points_ajoutes = self.env['ajouter.point'].search([('user_id', 'in', users.ids)])
        baremes = self.search([('type', '=', 'coefficient')])
        baremes_by_name_zone = {}
        for bareme in baremes:
            key = (bareme.name, bareme.zone_id.id if bareme.zone_id else False)
            baremes_by_name_zone[key] = bareme
        points_by_user = {}
        for point in all_points_ajoutes:
            user_id = point.user_id.id
            if user_id not in points_by_user:
                points_by_user[user_id] = []
            points_by_user[user_id].append(point)
        results = []
        for user in users:
            total_prime = 0
            details = {}
            agent_zones = user.zone_ids
            user_points = points_by_user.get(user.id, [])
            for point in user_points:
                bareme = None
                for zone in agent_zones:
                    key = (point.type_id.name, zone.id)
                    if key in baremes_by_name_zone:
                        bareme = baremes_by_name_zone[key]
                        break
                if not bareme:
                    key = (point.type_id.name, False)
                    bareme = baremes_by_name_zone.get(key)
                if bareme:
                    prime = point.nombre * bareme.coefficient
                    total_prime += prime
                    type_key = point.type_id.name.lower().replace(' ', '_')
                    if type_key in details:
                        details[type_key]['count'] += point.nombre
                        details[type_key]['points'] += prime
                    else:
                        details[type_key] = {'count': point.nombre, 'coefficient': bareme.coefficient, 'points': prime,
                                             'bareme_name': point.type_id.name}
                else:
                    type_key = point.type_id.name.lower().replace(' ', '_')
                    if type_key not in details:
                        details[type_key] = {'count': point.nombre, 'coefficient': 0, 'points': 0,
                                             'bareme_name': point.type_id.name + ' (Non trouvé)'}
            results.append({'user_id': user.id, 'user_name': user.name, 'total_prime': total_prime, 'details': details})
        return results

    def action_calculate_manual_prime(self):
        self.calculate_manual_points_prime()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Calcul des primes terminé', 'message': 'Vérifiez la console serveur',
                           'sticky': False, 'type': 'success'}}

    def get_agent_detailed_stats(self, user_id):
        user = self.env['res.users'].browse(user_id)
        all_livraisons = self.env['livraison'].search([('livrer_par_last', '=', user.id), ('stage', '=', 'livre')])
        all_depenses = self.env['depense.record'].search(
            [('caisse.user_id', '=', user.id), ('type_depense', '=', 1), ('status', '=', 'valide')])
        all_maintenances = self.env['maintenance.record'].search([('create_uid', '=', user.id)])
        agent_zones = user.zone_ids
        stats = {k: 0 for k in
                 ['lavage', 'livraison_normal', 'livraison_hors_zone', 'livraison_tardive', 'siege_bebe', 'conducteur',
                  'carburant', 'protection_standard', 'protection_max', 'maintenance', 'alerte', 'degradation']}
        stats['lavage'] = len(all_depenses)
        for lv in all_livraisons:
            is_tardif = False
            is_hors_zone = False
            if lv.date_de_livraison:
                heure = lv.date_de_livraison.hour if hasattr(lv.date_de_livraison, 'hour') else 0
                is_tardif = heure >= 19 or heure < 7
            if lv.lv_type == 'livraison' and lv.lieu_depart and lv.lieu_depart.zone:
                is_hors_zone = lv.lieu_depart.zone not in agent_zones
            elif lv.lv_type == 'restitution' and lv.lieu_retour and lv.lieu_retour.zone:
                is_hors_zone = lv.lieu_retour.zone not in agent_zones
            if is_tardif:
                stats['livraison_tardive'] += 1
            elif is_hors_zone:
                stats['livraison_hors_zone'] += 1
            else:
                stats['livraison_normal'] += 1
            if lv.lv_type == 'livraison':
                if lv.sb_ajout: stats['siege_bebe'] += 1
                if lv.nd_driver_ajoute: stats['conducteur'] += 1
                if lv.carburant_ajoute: stats['carburant'] += 1
                if lv.standart_ajoute: stats['protection_standard'] += 1
                if lv.max_ajoute: stats['protection_max'] += 1
            if lv.lv_type == 'restitution' and lv.degradation_limit_da:
                stats['degradation'] += lv.degradation_limit_da
        for maint in all_maintenances:
            if maint.alert_id:
                stats['alerte'] += 1
            else:
                stats['maintenance'] += 1
        return stats

    def action_get_agent_stats(self):
        users = self.env['res.users'].search([], limit=1)
        if users:
            stats = self.get_agent_detailed_stats(users[0].id)
            for key, value in stats.items():
                print(f"{key}: {value}")
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Statistiques calculées', 'message': 'Vérifiez la console serveur', 'sticky': False,
                           'type': 'info'}}

    def calculate_agent_points_with_ranking(self):
        """Version originale sans filtrage mois (pour rétrocompatibilité)"""
        return self.calculate_agent_points_with_ranking_monthly(None, None)

    def action_calculate_points_with_ranking(self):
        self.calculate_agent_points_with_ranking()
        return {'type': 'ir.actions.client', 'tag': 'display_notification',
                'params': {'title': 'Calcul des points avec classement terminé',
                           'message': 'Vérifiez la console serveur', 'sticky': False, 'type': 'success'}}

    # APRÈS
    @api.model
    def get_ranking_for_display(self, year=None, month=None):
        year, month = self._normalize_year_month(year, month)
        self_sudo = self.sudo()
        internal_results = self_sudo.calculate_agent_points_with_ranking_monthly(year, month)

        # APRÈS
        manual_results = self.calculate_manual_points_prime_monthly(year, month)

        ranking = []
        for agent in internal_results:
            manual = next((m for m in manual_results if m['user_id'] == agent['user_id']), None)
            prime_speciale = math.ceil(manual['total_prime'] * 100) if manual else 0
            prime_finale_reelle = agent.get('prime_services', 0) + prime_speciale

            ranking.append({
                'user_id': agent['user_id'],
                'user_name': agent['user_name'],
                'prime_finale': prime_finale_reelle,
                'prime_services': agent.get('prime_services', 0),
                'prime_speciale': prime_speciale,
                'is_premier_national': agent.get('is_premier_national', False),
                'is_premier_regional': agent.get('is_premier_regional', False),
            })

        ranking.sort(key=lambda x: x['prime_finale'], reverse=True)
        return ranking

    def _get_blocked_user_ids(self, year, month):
        """
        Retourne les IDs des agents bloqués pour le mois/année donné.
        Un agent est bloqué si sa période de blocage chevauche le mois en question.
        """
        from datetime import date as date_type

        first_day = date_type(year, month, 1)
        last_day = date_type(year, month, calendar.monthrange(year, month)[1])

        blocked = self.env['bloquer.agent'].search([
            ('active', '=', True),
            ('date_debut', '<=', last_day),
            ('date_fin', '>=', first_day),
        ])

        blocked_ids = blocked.mapped('user_id').ids
        if blocked_ids:
            print(f"🚫 Agents bloqués pour {month}/{year}: {blocked.mapped('user_id.name')}")
        return blocked_ids