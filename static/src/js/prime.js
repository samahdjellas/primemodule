/** @odoo-module **/
import { Component, useState, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class PrimeInterface extends Component {
    static template = "prime.PrimeTemplate";

    setup() {
    this.orm = useService("orm");
    this.state = useState({
        agents: [],
        selectedAgent: null,
        agentStats: null,
        baremes: [],
        loading: true,
        agentZonesDetails: {},
        ranking: []
    });

    onWillStart(async () => {
        await this.loadAgents();
        await this.loadBaremes();
        await this.loadAllAgentsRanking();

        // Charger les stats du premier agent par défaut
        if (this.state.agents.length > 0) {
            this.state.selectedAgent = this.state.agents[0];
            await this.loadAgentStats(this.state.agents[0].id);
        }
    });
}
    async onAgentChange(ev) {
    const agentId = parseInt(ev.target.value);
    const agent = this.state.agents.find(a => a.id === agentId);

    if (!agent) {
        console.error("Agent non trouvé");
        return;
    }

    this.state.selectedAgent = agent;
    console.log("Chargement des stats pour:", agent.name);

    // Afficher un indicateur de chargement
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
                [["type", "=", "coefficient"]],
                ["id", "name", "coefficient", "zone_id"]
            );
            this.state.baremes = baremes;
            console.log("Barèmes chargés:", baremes);
        } catch (error) {
            console.error("Erreur lors du chargement des barèmes:", error);
        }
    }

    async loadAgents() {
        try {
            const users = await this.orm.searchRead(
                "res.users",
                [],
                ["id", "name", "zone_ids"],
                { limit: 0 }
            );

            const agentsWithZones = await Promise.all(
                users.map(async (user) => {
                    let zoneIds = [];
                    let zoneDetails = [];

                    if (user.zone_ids && user.zone_ids.length > 0) {
                        // Récupérer les détails des zones
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
                // Stocker les zones de l'agent pour référence
                this.state.agentZonesDetails[agentsWithZones[0].id] = agentsWithZones[0].zoneDetails;
            }
            this.state.loading = false;
            console.log("Agents chargés:", agentsWithZones);
        } catch (error) {
            console.error("Erreur lors du chargement des agents:", error);
            this.state.loading = false;
        }
    }

    async loadAgentStats(userId) {
    try {
        console.log("=== CHARGEMENT STATS POUR USER:", userId, "===");

        // Vérifier que l'agent existe
        const agent = this.state.agents.find(a => a.id === userId);
        if (!agent) {
            console.error("Agent non trouvé pour userId:", userId);
            this.state.agentStats = {
                stats: {},
                totalPoints: 0,
                manualStats: {},
                totalManualPrime: 0,
                isPremierNational: false,
                isPremierRegional: false, // ← AJOUTER ICI
                agentName: 'Agent non trouvé',
                zonesText: 'N/A'
            };
            return;
        }

        // 1. Charger les statistiques internes avec ranking
        const baremeId = 1;
        const internalResults = await this.orm.call(
            "bareme.prime",
            "calculate_agent_points_with_ranking",
            [baremeId]
        );

        console.log("Résultats internes:", internalResults);

        // Trouver les résultats pour cet agent spécifique
        const agentInternalResult = internalResults.find(r => r.user_id === userId);

        // Initialiser les statistiques avec valeurs par défaut
        const stats = {};
        const allStatKeys = [
            'lavage', 'livraison_normal', 'livraison_hors_zone', 'livraison_tardive',
            'maintenance', 'alerte', 'siege_bebe', 'conducteur', 'carburant',
            'protection_standard', 'protection_max', 'premier_national', 'premier_regional' // ← AJOUTER premier_regional
        ];

        // Initialiser toutes les statistiques avec des valeurs par défaut
        allStatKeys.forEach(key => {
            stats[key] = {
                count: 0,
                points: 0,
                coefficient: 0,
                bareme_name: 'Non défini'
            };
        });

        // Remplir avec les données réelles si disponibles
        if (agentInternalResult && agentInternalResult.details) {
            // Mettre à jour les statistiques existantes
            Object.keys(agentInternalResult.details).forEach(key => {
                if (stats[key]) {
                    stats[key] = {
                        count: agentInternalResult.details[key].count || 0,
                        points: agentInternalResult.details[key].points || 0,
                        coefficient: agentInternalResult.details[key].coefficient || 0,
                        bareme_name: agentInternalResult.details[key].bareme_name || 'Non défini'
                    };
                }
            });

            // S'assurer que premier_national est bien défini
            if (agentInternalResult.is_premier_national && !stats.premier_national.count) {
                // Chercher le barème Premier National pour avoir les bonnes informations
                const premierBareme = this.state.baremes.find(b =>
                    b.name.toLowerCase().includes('premier') &&
                    b.name.toLowerCase().includes('national')
                );

                if (premierBareme) {
                    stats.premier_national = {
                        count: 1,
                        points: premierBareme.coefficient || 0,
                        coefficient: premierBareme.coefficient || 0,
                        bareme_name: premierBareme.name || 'Premier National'
                    };
                } else {
                    stats.premier_national = {
                        count: 1,
                        points: 0,
                        coefficient: 0,
                        bareme_name: 'Premier National 🏆'
                    };
                }
            }

            // S'assurer que premier_regional est bien défini
            if (agentInternalResult.is_premier_regional && !stats.premier_regional.count) {
                // Chercher le barème Premier Régional
                const premierRegionalBareme = this.state.baremes.find(b =>
                    b.name.toLowerCase().includes('premier') &&
                    b.name.toLowerCase().includes('régional')
                );

                if (premierRegionalBareme) {
                    stats.premier_regional = {
                        count: 1,
                        points: premierRegionalBareme.coefficient || 0,
                        coefficient: premierRegionalBareme.coefficient || 0,
                        bareme_name: premierRegionalBareme.name || 'Premier Régional'
                    };
                } else {
                    stats.premier_regional = {
                        count: 1,
                        points: 0,
                        coefficient: 0,
                        bareme_name: 'Premier Régional 🥈'
                    };
                }
            }
        }

        console.log("Stats formatées:", stats);

        // 2. Charger les points manuels
        const manualResults = await this.orm.call(
            "bareme.prime",
            "calculate_manual_points_prime",
            [baremeId]
        );

        console.log("Résultats manuels:", manualResults);

        // Trouver les résultats manuels pour cet agent
        const agentManualResult = manualResults.find(r => r.user_id === userId);

        // Initialiser les statistiques manuelles
        const manualStats = {};
        if (agentManualResult && agentManualResult.details) {
            // Convertir l'objet details en format standard
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

        console.log("Stats manuelles formatées:", manualStats);

        // 3. Calculer les totaux
        const totalPoints = agentInternalResult ? agentInternalResult.total_points : 0;
        const totalManualPrime = agentManualResult ? agentManualResult.total_prime : 0;
        const isPremierNational = agentInternalResult ? (agentInternalResult.is_premier_national || false) : false;
        const isPremierRegional = agentInternalResult ? (agentInternalResult.is_premier_regional || false) : false; // ← AJOUTER ICI

        // 4. Mettre à jour le state
        this.state.agentStats = {
            stats: stats,
            totalPoints: totalPoints,
            manualStats: manualStats,
            totalManualPrime: totalManualPrime,
            isPremierNational: isPremierNational,
            isPremierRegional: isPremierRegional, // ← AJOUTER ICI
            agentName: agent.name,
            zonesText: agent.zonesText,
            agentId: agent.id,
            // Informations détaillées pour le débogage
            _debug: {
                internalResult: agentInternalResult,
                manualResult: agentManualResult,
                allInternalResults: internalResults,
                allManualResults: manualResults
            }
        };

        console.log("AgentStats final:", this.state.agentStats);
        console.log("Premier National:", isPremierNational);
        console.log("Premier Régional:", isPremierRegional);

    } catch (error) {
        console.error("Erreur détaillée dans loadAgentStats:", error);
        console.error("Stack trace:", error.stack);

        // En cas d'erreur, initialiser avec des valeurs par défaut
        const agent = this.state.agents.find(a => a.id === userId);

        this.state.agentStats = {
            stats: {},
            totalPoints: 0,
            manualStats: {},
            totalManualPrime: 0,
            isPremierNational: false,
            isPremierRegional: false, // ← AJOUTER ICI
            agentName: agent ? agent.name : 'Erreur',
            zonesText: agent ? agent.zonesText : 'N/A',
            agentId: userId,
            _error: {
                message: error.message,
                timestamp: new Date().toISOString()
            }
        };
    }

}

    // Méthode pour vérifier si un barème correspond à une statistique
    getManualStatDisplay(statKey) {
    if (!this.state.agentStats ||
        !this.state.agentStats.manualStats ||
        !this.state.agentStats.manualStats[statKey]) {
        return {
            count: 0,
            coefficient: 0,
            points: 0,
            baremeName: "Non défini"
        };
    }
    return this.state.agentStats.manualStats[statKey];
}

getTotalManualPrime() {
    if (!this.state.agentStats) return 0;
    return this.state.agentStats.totalManualPrime;
}

getTotalManualPoints() {
    if (!this.state.agentStats || !this.state.agentStats.manualStats) return 0;

    let total = 0;
    Object.values(this.state.agentStats.manualStats).forEach(stat => {
        total += stat.points || 0;
    });
    return total;
}
    isBaremeForStat(baremeName, statKey) {
        const baremeNameLower = baremeName.toLowerCase();

        // Mapping précis des statistiques
        if (statKey === 'lavage') {
            return baremeNameLower.includes('lavage');
        }
        else if (statKey === 'livraison_normal') {
            return baremeNameLower.includes('livraison normal') ||
                   baremeNameLower.includes('livraison/restitution') ||
                   baremeNameLower.includes('livraison zone');
        }
        else if (statKey === 'livraison_hors_zone') {
            return baremeNameLower.includes('hors zone') ||
                   baremeNameLower.includes('hors_zone');
        }
        else if (statKey === 'livraison_tardive') {
            return baremeNameLower.includes('tardif') ||
                   baremeNameLower.includes('tardive');
        }
        else if (statKey === 'maintenance') {
            return baremeNameLower.includes('maintenance') &&
                   !baremeNameLower.includes('alert');
        }
        else if (statKey === 'alerte') {
            return baremeNameLower.includes('alert');
        }
        else if (statKey === 'siege_bebe') {
            return baremeNameLower.includes('siege') ||
                   baremeNameLower.includes('bebe') ||
                   baremeNameLower.includes('siège');
        }
        else if (statKey === 'conducteur') {
            return baremeNameLower.includes('2eme conducteur') ||
                   baremeNameLower.includes('2ème conducteur') ||
                   (baremeNameLower.includes('conducteur') && !baremeNameLower.includes('2eme') && !baremeNameLower.includes('2ème'));
        }
        else if (statKey === 'carburant') {
            return baremeNameLower.includes('carburant');
        }
        else if (statKey === 'protection_standard') {
            return baremeNameLower.includes('protection standard') ||
                   (baremeNameLower.includes('standard') && baremeNameLower.includes('protection'));
        }
        else if (statKey === 'protection_max') {
            return baremeNameLower.includes('protection max') ||
                   (baremeNameLower.includes('max') && baremeNameLower.includes('protection'));
        }

        return false;
    }

    async onAgentChange(ev) {
        const agentId = parseInt(ev.target.value);
        const agent = this.state.agents.find(a => a.id === agentId);

        if (!agent) {
            console.error("Agent non trouvé");
            return;
        }

        this.state.selectedAgent = agent;
        console.log("Agent changé vers:", agent.name);

        await this.loadAgentStats(agentId);
    }

    getAgentInitials(name) {
        if (!name) return "?";
        const parts = name.split(" ");
        if (parts.length >= 2) {
            return parts[0][0] + parts[1][0];
        }
        return name[0];
    }
    getTotalFinalPrime() {
    if (!this.state.agentStats) return 0;

    // Prime Services = totalPoints * 100
    const primeServices = (this.state.agentStats.totalPoints || 0) * 100;

    // Prime Spéciale = totalManualPrime
    const primeSpeciale = this.state.agentStats.totalManualPrime || 0;

    // Total Final
    return primeServices + primeSpeciale;
}

    getStatDisplay(statKey) {
    if (!this.state.agentStats ||
        !this.state.agentStats.stats ||
        !this.state.agentStats.stats[statKey]) {
        return {
            count: 0,
            coefficient: 0,
            points: 0,
            baremeName: "Non défini"
        };
    }
    return this.state.agentStats.stats[statKey];
}
    async loadAllAgentsRanking() {
    try {
        const baremeId = 1;

        const internalResults = await this.orm.call(
            "bareme.prime",
            "calculate_agent_points_with_ranking",
            [baremeId]
        );

        const manualResults = await this.orm.call(
            "bareme.prime",
            "calculate_manual_points_prime",
            [baremeId]
        );

        // Calculer la prime totale pour chaque agent
        const agentsWithPrimes = this.state.agents.map(agent => {
            const internalData = internalResults.find(r => r.user_id === agent.id);
            const manualData = manualResults.find(r => r.user_id === agent.id);

            const primeServices = (internalData?.total_points || 0) * 100;
            const primeSpeciale = manualData?.total_prime || 0;
            const primeFinale = (internalData?.prime_totale || primeServices) + primeSpeciale;
            const totalPoints = (internalData?.total_points || 0);

            const isPremierNational = internalData?.is_premier_national || false;
            const isPremierRegional = internalData?.is_premier_regional || false;

            // Calculer les bonus
            let bonusPremierNational = 0;
            let bonusPremierRegional = 0;

            if (isPremierNational && internalData?.details?.premier_national) {
                bonusPremierNational = internalData.details.premier_national.points * 100;
            }

            if (isPremierRegional && internalData?.details?.premier_regional) {
                bonusPremierRegional = internalData.details.premier_regional.points * 100;
            }

            return {
                id: agent.id,
                name: agent.name,
                zoneIds: agent.zone_ids || [],
                totalPoints: totalPoints,
                primeServices: primeServices,
                primeSpeciale: primeSpeciale,
                primeFinale: primeFinale + bonusPremierNational + bonusPremierRegional,
                performance: this.getPerformanceLevel(primeFinale),
                isPremierNational: isPremierNational,
                isPremierRegional: isPremierRegional,
                bonusPremierNational: bonusPremierNational,
                bonusPremierRegional: bonusPremierRegional
            };
        });

        // Trier par prime finale décroissante
        agentsWithPrimes.sort((a, b) => b.primeFinale - a.primeFinale);

        this.state.ranking = agentsWithPrimes;

        console.log("Classement chargé avec Premiers Nationaux/Régionaux:", agentsWithPrimes);
    } catch (error) {
        console.error("Erreur lors du chargement du classement:", error);
        this.state.ranking = [];
    }
}
isPremierRegional() {
    return this.state.agentStats?.isPremierRegional || false;
}

getPerformanceLevel(prime) {
    if (prime >= 40000) return { label: 'Excellent', class: 'excellent' };
    if (prime >= 30000) return { label: 'Bon', class: 'bon' };
    if (prime >= 20000) return { label: 'Moyen', class: 'moyen' };
    return { label: 'À améliorer', class: 'ameliorer' };
}
getBonusPremierNational() {
    if (!this.state.agentStats || !this.state.agentStats.isPremierNational) return 0;

    // Le bonus est déjà dans les stats
    if (this.state.agentStats.stats?.premier_national) {
        return this.state.agentStats.stats.premier_national.points * 100; // Convertir en DA
    }
    return 0;
}

isPremierNational() {
    return this.state.agentStats?.isPremierNational || false;
}
isPremierRegional() {
    if (!this.state.selectedAgent || !this.state.agentStats) return false;
    return this.state.agentStats.isPremierRegional || false;
}
// Ajouter ces méthodes dans la classe PrimeInterface

isDoublePremier() {
    return this.isPremierNational() && this.isPremierRegional();
}

getDoublePremierMessage() {
    if (this.isDoublePremier()) {
        return "🏆🥈 DOUBLE CHAMPION : Premier National & Premier Régional !";
    }
    return "";
}

getTotalFinalPrime() {
    if (!this.state.agentStats) return 0;

    const primeServices = (this.state.agentStats.totalPoints || 0) * 100;
    const primeSpeciale = this.state.agentStats.totalManualPrime || 0;
    const bonusPremierNational = this.getBonusPremierNational();
    const bonusPremierRegional = this.getBonusPremierRegional();

    // Un agent peut avoir les deux bonus maintenant !
    return primeServices + primeSpeciale + bonusPremierNational + bonusPremierRegional;
}

getTotalFinalPrime() {
    if (!this.state.agentStats) return 0;

    const primeServices = (this.state.agentStats.totalPoints || 0) * 100;
    const primeSpeciale = this.state.agentStats.totalManualPrime || 0;
    const bonusPremierNational = this.getBonusPremierNational();
    const bonusPremierRegional = this.getBonusPremierRegional();

    return primeServices + primeSpeciale + bonusPremierNational + bonusPremierRegional;
}
    getBonusPremierRegional() {
    if (!this.state.agentStats || !this.state.agentStats.isPremierRegional) return 0;

    if (this.state.agentStats.stats?.premier_regional) {
        return this.state.agentStats.stats.premier_regional.points * 100;
    }
    return 0;
}
    getTotalPrime() {
        if (!this.state.agentStats) return 0;
        return this.state.agentStats.totalPoints * 100; // 100 DA par point
    }
}

registry.category("actions").add("prime_interface_action", PrimeInterface);