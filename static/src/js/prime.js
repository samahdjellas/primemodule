/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PrimeInterface extends Component {
    static template = "prime.PrimeTemplate";

    // APRÈS
static STAT_KEYS_WITH_TOTAL = ['conducteur', 'carburant', 'protection_standard', 'protection_max', 'klm_illimite', 'siege_bebe'];

    setup() {
        this.orm = useService("orm");
        this.state = useState({
            agents: [],
            selectedAgent: null,
            agentStats: null,
            baremes: [],
            loading: true,
            tauxChange: null,
            agentZonesDetails: {},
            ranking: [],

            isCurrentUserAgent: false,  // ← NOUVEAU
            currentUserId: null,        // ← NOUVEAU

            selectedYear: null,
            selectedMonth: null,
            years: [],
            months: [
                { id: 1, name: "Janvier" },
                { id: 2, name: "Février" },
                { id: 3, name: "Mars" },
                { id: 4, name: "Avril" },
                { id: 5, name: "Mai" },
                { id: 6, name: "Juin" },
                { id: 7, name: "Juillet" },
                { id: 8, name: "Août" },
                { id: 9, name: "Septembre" },
                { id: 10, name: "Octobre" },
                { id: 11, name: "Novembre" },
                { id: 12, name: "Décembre" }
            ],
            currentMonthName: "",
            periodDisplay: ""
        });

        onWillStart(async () => {
            await this.initializeDateFilters();
            await this.checkCurrentUserRole(); // ← NOUVEAU (avant loadAgents)
            await this.loadAgents();
            await this.loadBaremes();
            await this.loadTauxChange();
            await this.loadAllAgentsRanking();

            if (this.state.agents.length > 0) {
                this.state.selectedAgent = this.state.agents[0];
                await this.loadAgentStats(this.state.agents[0].id);
            }
        });
    }

    // ← NOUVELLE MÉTHODE
    async checkCurrentUserRole() {
        try {
            const currentUserId = this.env.services.user.userId;
            this.state.currentUserId = currentUserId;

            const session = await this.orm.searchRead(
                "res.users",
                [["id", "=", currentUserId]],
                ["id", "groups_id"],
                { limit: 1 }
            );
            if (!session || session.length === 0) return;

            let agentGroupId = null;
            try {
                const irModelData = await this.orm.searchRead(
                    "ir.model.data",
                    [["module", "=", "access_rights_groups"], ["name", "=", "group_agent"]],
                    ["res_id"]
                );
                if (irModelData?.length > 0) agentGroupId = irModelData[0].res_id;
            } catch (e) {}

            if (!agentGroupId) {
                const agentGroup = await this.orm.searchRead(
                    "res.groups",
                    [["name", "=", "AGENT"]],
                    ["id"],
                    { limit: 1 }
                );
                if (agentGroup?.length > 0) agentGroupId = agentGroup[0].id;
            }

            if (!agentGroupId) {
                const agentGroup = await this.orm.searchRead(
                    "res.groups",
                    [["name", "ilike", "agent"]],
                    ["id"],
                    { limit: 1 }
                );
                if (agentGroup?.length > 0) agentGroupId = agentGroup[0].id;
            }

            this.state.isCurrentUserAgent =
                agentGroupId !== null &&
                session[0].groups_id.includes(agentGroupId);

            console.log(`✅ isCurrentUserAgent = ${this.state.isCurrentUserAgent}`);

        } catch (error) {
            console.error("Erreur checkCurrentUserRole:", error);
            this.state.isCurrentUserAgent = false;
        }
    }

    async initializeDateFilters() {
        const currentDate = new Date();
        const currentYear = currentDate.getFullYear();
        const currentMonth = currentDate.getMonth() + 1;

        const years = [];
        for (let i = currentYear - 2; i <= currentYear + 1; i++) {
            years.push(i);
        }

        this.state.years = years;
        this.state.selectedYear = currentYear;
        this.state.selectedMonth = currentMonth;
        this.state.currentMonthName = this.getMonthName(currentMonth);
        this.state.periodDisplay = `${this.getMonthName(currentMonth)} ${currentYear}`;
    }

    _buildPeriodArgs() {
        const year  = this.state.selectedYear  ? parseInt(this.state.selectedYear,  10) : null;
        const month = this.state.selectedMonth ? parseInt(this.state.selectedMonth, 10) : null;

        console.log(`📅 _buildPeriodArgs → year=${year}, month=${month}`);

        if (year !== null && month !== null) {
            if (year > 2000 && month >= 1 && month <= 12) {
                console.log(`✅ Ordre correct → [${year}, ${month}]`);
                return [year, month];
            } else {
                console.error(`❌ Valeurs incohérentes : year=${year}, month=${month}`);
                const now = new Date();
                return [now.getFullYear(), now.getMonth() + 1];
            }
        }

        const now = new Date();
        return [now.getFullYear(), now.getMonth() + 1];
    }

    onMonthChange(ev) {
        const value = ev.target.value;
        if (!value || value === "") {
            this.state.selectedMonth = null;
        } else {
            this.state.selectedMonth = parseInt(value, 10);
        }
        this.updatePeriodDisplay();
    }

    onYearChange(ev) {
        const value = ev.target.value;
        if (!value || value === "") {
            this.state.selectedYear = null;
        } else {
            this.state.selectedYear = parseInt(value, 10);
        }
        this.updatePeriodDisplay();
    }

    updatePeriodDisplay() {
        if (this.state.selectedYear && this.state.selectedMonth) {
            this.state.periodDisplay = `${this.getMonthName(this.state.selectedMonth)} ${this.state.selectedYear}`;
        } else if (this.state.selectedYear && !this.state.selectedMonth) {
            this.state.periodDisplay = `Année ${this.state.selectedYear}`;
        } else if (!this.state.selectedYear && this.state.selectedMonth) {
            this.state.periodDisplay = `${this.getMonthName(this.state.selectedMonth)} (toutes années)`;
        } else {
            this.state.periodDisplay = "Toutes les données";
        }

        console.log(`📅 Période sélectionnée: ${this.state.periodDisplay} → year=${this.state.selectedYear}, month=${this.state.selectedMonth}`);
    }

    async onRefreshClick() {
        await this.reloadAllData();
    }

    async reloadAllData() {
        this.state.loading = true;
        this.state.agentStats = null;

        if (this.state.selectedAgent) {
            await this.loadAgentStats(this.state.selectedAgent.id);
        }

        await this.loadAllAgentsRanking();
        this.state.loading = false;
    }

    async loadAgents() {
        try {
            let groupId = null;

            try {
                const irModelData = await this.orm.searchRead(
                    "ir.model.data",
                    [["module", "=", "access_rights_groups"], ["name", "=", "group_agent"]],
                    ["res_id"]
                );
                if (irModelData && irModelData.length > 0) {
                    groupId = irModelData[0].res_id;
                    console.log("✅ Groupe trouvé par XML ID:", groupId);
                }
            } catch (e) {
                console.log("XML ID non trouvé, essai par nom...");
            }

            if (!groupId) {
                const agentGroup = await this.orm.searchRead(
                    "res.groups",
                    [["name", "=", "AGENT"]],
                    ["id"],
                    { limit: 1 }
                );
                if (agentGroup && agentGroup.length > 0) {
                    groupId = agentGroup[0].id;
                    console.log("✅ Groupe trouvé par nom exact:", groupId);
                }
            }

            if (!groupId) {
                const agentGroup = await this.orm.searchRead(
                    "res.groups",
                    [["name", "ilike", "agent"]],
                    ["id"],
                    { limit: 1 }
                );
                if (agentGroup && agentGroup.length > 0) {
                    groupId = agentGroup[0].id;
                    console.log("✅ Groupe trouvé par recherche approximative:", groupId);
                }
            }

            if (!groupId) {
                console.error("❌ Groupe AGENT non trouvé dans le système");
                this.state.agents = [];
                this.state.loading = false;
                return;
            }

            // ← MODIFICATION : si l'utilisateur est agent, on ne charge que lui
            let users;
            if (this.state.isCurrentUserAgent) {
                users = await this.orm.searchRead(
                    "res.users",
                    [["id", "=", this.state.currentUserId]],
                    ["id", "name", "zone_ids"],
                    { limit: 1 }
                );
                console.log("🔒 Mode agent : limité à l'utilisateur connecté");
            } else {
                users = await this.orm.searchRead(
                    "res.users",
                    [["groups_id", "in", [groupId]]],
                    ["id", "name", "zone_ids"],
                    { limit: 0 }
                );
                console.log(`✅ ${users.length} agents trouvés dans le groupe`);
            }

            const agentsWithZones = await Promise.all(
                users.map(async (user) => {
                    let zoneIds = [];
                    let zoneDetails = [];

                    if (user.zone_ids && user.zone_ids.length > 0) {
                        const zones = await this.orm.searchRead(
                            "zone",
                            [["id", "in", user.zone_ids]],
                            ["id", "name"]
                        );
                        zoneIds = zones.map(z => z.id);
                        zoneDetails = zones;
                    }

                    return {
                        id: user.id,
                        name: user.name,
                        zone_ids: zoneIds,
                        zoneDetails: zoneDetails,
                        zonesText: zoneDetails.length > 0 ?
                            zoneDetails.map(z => z.name).join(", ") : "Aucune zone"
                    };
                })
            );

            this.state.agents = agentsWithZones;

            if (agentsWithZones.length > 0) {
                this.state.selectedAgent = agentsWithZones[0];
                this.state.agentZonesDetails[agentsWithZones[0].id] = agentsWithZones[0].zoneDetails;
            }

            this.state.loading = false;
            console.log("✅ Agents chargés avec succès");

        } catch (error) {
            console.error("❌ Erreur lors du chargement des agents:", error);
            this.state.agents = [];
            this.state.loading = false;
        }
    }

    async loadTauxChange() {
        try {
            const records = await this.orm.searchRead(
                'taux.change',
                [],
                ['montant', 'name'],
                { limit: 1, order: 'id desc' }
            );
            if (records && records.length > 0 && records[0].montant > 0) {
                this.state.tauxChange = records[0].montant;
                console.log(`✅ Taux EUR/DZD: ${this.state.tauxChange}`);
            } else {
                this.state.tauxChange = 1.0;
                console.warn('⚠️ Taux non trouvé, fallback 1.0');
            }
        } catch (e) {
            console.error('Erreur taux de change:', e);
            this.state.tauxChange = 1.0;
        }
    }

    async onAgentChange(ev) {
        const agentId = parseInt(ev.target.value, 10);
        const agent = this.state.agents.find(a => a.id === agentId);

        if (!agent) {
            console.error("Agent non trouvé");
            return;
        }

        this.state.selectedAgent = agent;
        this.state.agentStats = null;

        try {
            await this.loadAgentStats(agentId);
        } catch (error) {
            console.error("Erreur lors du chargement des stats:", error);
        }
    }

    async loadBaremes() {
        try {
            const baremes = await this.orm.searchRead(
                "bareme.prime",
                [],
                ["id", "name", "coefficient", "valeur_pourcentage", "type", "zone_id"]
            );
            this.state.baremes = baremes;
            console.log("Barèmes chargés:", baremes.length);
        } catch (error) {
            console.error("Erreur lors du chargement des barèmes:", error);
        }
    }

    async loadAgentStats(userId) {
        try {
            const periodArgs = this._buildPeriodArgs();
            console.log(`=== CHARGEMENT STATS POUR USER: ${userId} - PÉRIODE: year=${periodArgs[0]}, month=${periodArgs[1]} ===`);

            const agent = this.state.agents.find(a => a.id === userId);
            if (!agent) {
                console.error("Agent non trouvé pour userId:", userId);
                return;
            }

            const internalResults = await this.orm.call(
                "bareme.prime",
                "calculate_agent_points_with_ranking_monthly",
                [periodArgs[0], periodArgs[1]]
            );

            const agentInternalResult = internalResults.find(r => r.user_id === userId);

            const stats = {};
            const allStatKeys = [
                'lavage', 'livraison_normal', 'livraison_hors_zone', 'livraison_tardive', 'livraison_hors_zone_tardive',
                'maintenance', 'alerte', 'siege_bebe', 'conducteur', 'carburant',
                'protection_standard', 'livraison_hors_ville', 'protection_max', 'premier_national', 'premier_regional',
                 'klm_illimite' ,'degradation'
            ];

            allStatKeys.forEach(key => {
                stats[key] = {
                    count: 0, points: 0, coefficient: 0, coefficientDisplay: '0',
                    bareme_name: 'Non défini', type: 'coefficient', total_amount: 0, prime_da: 0
                };
            });

            if (agentInternalResult && agentInternalResult.details) {
                Object.keys(agentInternalResult.details).forEach(key => {
                    if (stats[key] !== undefined) {
                        const detail = agentInternalResult.details[key];
                        const coefficient = detail.coefficient || 0;
                        const type = detail.type || 'coefficient';
                        // APRÈS
// APRÈS
stats[key] = {
    count: detail.count || 0,
    points: detail.points || 0,
    coefficient: coefficient,
    coefficientDisplay: type === 'pourcentage' ? `${coefficient}%` : `${coefficient}`,
    bareme_name: detail.bareme_name || 'Non défini',
    type: type,
    total_amount: detail.total_amount || 0,
    total_amount_dzd: detail.total_amount_dzd || 0,
    total_amount_brut: detail.total_amount_brut || 0,
    total_penalit_carburant: detail.total_penalit_carburant || 0,
    total_penalit_klm: detail.total_penalit_klm || 0,
    zone_name: detail.zone_name || 'Global',
    prime_da: detail.prime_da || 0
};
                    }
                });
            }

            const manualResults = await this.orm.call(
                "bareme.prime",
                "calculate_manual_points_prime_monthly",
                [periodArgs[0], periodArgs[1]]
            );

            const agentManualResult = manualResults.find(r => r.user_id === userId);

            const manualStats = {};
            if (agentManualResult && agentManualResult.details) {
                Object.keys(agentManualResult.details).forEach(key => {
                    const detail = agentManualResult.details[key];
                    manualStats[key] = {
                        count: detail.count || 0,
                        points: detail.points || 0,
                        coefficient: detail.coefficient || 0,
                        bareme_name: detail.bareme_name || 'Non défini'
                    };
                });
            }

            const totalPoints           = agentInternalResult?.total_points           || 0;
            const totalPrimePourcentage = agentInternalResult?.total_prime_pourcentage || 0;
            const primePoints           = agentInternalResult?.prime_points            || 0;
            const primePourcentage      = agentInternalResult?.prime_pourcentage       || 0;
            const primeServices         = agentInternalResult?.prime_services          || 0;
            const totalManualPrime      = (agentManualResult?.total_prime || 0) * 100;
            const isPremierNational     = agentInternalResult?.is_premier_national     || false;
            const isPremierRegional     = agentInternalResult?.is_premier_regional     || false;

            this.state.agentStats = {
                stats, totalPoints, totalPrimePourcentage, primePoints,
                primePourcentage, primeServices, manualStats, totalManualPrime,
                isPremierNational, isPremierRegional,
                agentName: agent.name,
                zonesText: agent.zonesText,
                agentId: agent.id,
                period: this.state.periodDisplay
            };

            console.log(`✅ Stats chargées pour ${agent.name} — ${this.state.periodDisplay}`);

        } catch (error) {
            console.error("Erreur dans loadAgentStats:", error);
            const agent = this.state.agents.find(a => a.id === userId);
            this.state.agentStats = {
                stats: {}, totalPoints: 0, totalPrimePourcentage: 0,
                primePoints: 0, primePourcentage: 0, primeServices: 0,
                manualStats: {}, totalManualPrime: 0,
                isPremierNational: false, isPremierRegional: false,
                agentName: agent ? agent.name : 'Erreur',
                zonesText: agent ? agent.zonesText : 'N/A',
                agentId: userId,
                period: this.state.periodDisplay
            };
        }
    }

    async loadAllAgentsRanking() {
    try {
        const periodArgs = this._buildPeriodArgs();

        const rankingData = await this.orm.call(
            "bareme.prime",
            "get_ranking_for_display",
            [periodArgs[0], periodArgs[1]]
        );

        this.state.ranking = rankingData.map(agent => ({
            id: agent.user_id,
            name: agent.user_name,
            primeFinale: agent.prime_finale,
            primeServices: agent.prime_services,
            primeSpeciale: agent.prime_speciale,
            isPremierNational: agent.is_premier_national,
            isPremierRegional: agent.is_premier_regional,
            performance: this.getPerformanceLevel(agent.prime_finale),
        }));

    } catch (error) {
        console.error("Erreur classement:", error);
        this.state.ranking = [];
    }
}

    // ========== MÉTHODES POUR PRIME DIVERS ==========

    getTotalManualPoints() {
    if (!this.state.agentStats?.manualStats) return 0;
    let total = 0;
    for (const key of Object.keys(this.state.agentStats.manualStats)) {
        total += this.state.agentStats.manualStats[key].points || 0;
    }
    return total;
}

    getTotalManualPrime() {
    return this.state.agentStats?.totalManualPrime || 0;
}

    // ========== MÉTHODES UTILITAIRES ==========

    getManualStatDisplay(statKey) {
        if (!this.state.agentStats?.manualStats?.[statKey]) {
            return { count: 0, coefficient: 0, points: 0, baremeName: "Non défini" };
        }
        return this.state.agentStats.manualStats[statKey];
    }

    getAgentInitials(name) {
        if (!name) return "?";
        const parts = name.split(" ");
        return parts.length >= 2 ? parts[0][0] + parts[1][0] : name[0];
    }

    getTotalFinalPrime() {
    if (!this.state.agentStats) return 0;
    return this.getPrimeServices() + this.state.agentStats.totalManualPrime;
}

    getStatDisplay(statKey) {
        if (!this.state.agentStats?.stats?.[statKey]) {
            return {
                count: 0, coefficient: 0, coefficientDisplay: '0', points: 0,
                baremeName: "Non défini", type: "coefficient", total_amount: 0,
                zone_name: "Global", prime_da: 0
            };
        }
        return this.state.agentStats.stats[statKey];
    }

    usesTotalAmount(statKey) {
        return PrimeInterface.STAT_KEYS_WITH_TOTAL.includes(statKey)
            && this.getStatDisplay(statKey).type === 'pourcentage';
    }

    getTotalAmountFormatted(statKey) {
        const stat = this.getStatDisplay(statKey);
        if (PrimeInterface.STAT_KEYS_WITH_TOTAL.includes(statKey) && stat.total_amount > 0) {
            return stat.total_amount.toLocaleString('fr-DZ');
        }
        return null;
    }

    getDegradationDisplay() {
        return this.getStatDisplay('degradation');
    }

    getPerformanceLevel(prime) {
        if (prime >= 30000) return { label: 'Excellent', class: 'excellent' };
        if (prime >= 20000) return { label: 'Bon', class: 'bon' };
        if (prime >= 10000) return { label: 'Moyen', class: 'moyen' };
        return { label: 'À améliorer', class: 'ameliorer' };
    }

    isPremierNational() {
        return this.state.agentStats?.isPremierNational || false;
    }

    isPremierRegional() {
        return this.state.agentStats?.isPremierRegional || false;
    }

    getPrimePoints() {
        return this.state.agentStats?.primePoints || 0;
    }

    getPrimePourcentage() {
        return this.state.agentStats?.primePourcentage || 0;
    }

    getPrimeServices() {
        return this.state.agentStats?.primeServices || 0;
    }

    getTotalPoints() {
        return this.state.agentStats?.totalPoints || 0;
    }

    getDegradationFormatted() {
        const degradation = this.getDegradationDisplay();
        if (degradation.type === 'pourcentage') {
            return `${degradation.total_amount.toLocaleString('fr-DZ')} DA × ${degradation.coefficientDisplay}`;
        } else {
            return `${degradation.count} × ${degradation.coefficientDisplay}`;
        }
    }

    getMonthName(monthId) {
        const month = this.state.months.find(m => m.id === monthId);
        return month ? month.name : "Mois inconnu";
    }
}

registry.category("actions").add("prime_interface_action", PrimeInterface);