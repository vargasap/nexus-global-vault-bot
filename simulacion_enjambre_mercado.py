import random
import numpy as np
import json

# ==============================================================================
# SIMULADOR MULTI-AGENTE DE MERCADO (ENFOQUE ENJAMBRE TIPO MIROFISH AI)
# Modela 10,000 agentes sintéticos de diferentes países, perfiles económicos
# y patrones de uso frente a la oferta de @nexus_global_vault_bot
# ==============================================================================

class SyntheticUserAgent:
    def __init__(self, agent_id):
        self.id = agent_id
        # Perfiles demográficos / geográficos
        # Latam/España: 45%, USA/Global West: 25%, Rusia/Europa Este: 15%, Asia/Otros: 15%
        self.region = random.choices(["LATAM_ES", "US_EU", "RU_EE", "GLOBAL"], weights=[45, 25, 15, 15])[0]
        
        # Necesidad de la herramienta:
        # Creador/Editor: 25%, Usuario Casual de Redes: 55%, Estudiante/Oficina: 20%
        self.intent = random.choices(["creator", "casual", "student_office"], weights=[25, 55, 20])[0]

        # Sensibilidad al precio (Capacidad y disposición a pagar en Stars con Apple/Google Pay):
        # 0: Solo quiere lo gratis (freebie seeker)
        # 1: Dispuesto a micropagos ($0.99 - $2.99)
        # 2: Heavy user / Power user (compra VIP $9.99 sin dudar)
        if self.region == "US_EU":
            self.willingness_to_pay = random.choices([0, 1, 2], weights=[50, 35, 15])[0]
        elif self.region == "LATAM_ES":
            self.willingness_to_pay = random.choices([0, 1, 2], weights=[70, 24, 6])[0]
        elif self.region == "RU_EE":
            self.willingness_to_pay = random.choices([0, 1, 2], weights=[55, 33, 12])[0]
        else:
            self.willingness_to_pay = random.choices([0, 1, 2], weights=[65, 28, 7])[0]

        # Probabilidad de compartir (K-factor viral)
        self.viral_share_rate = 0.08 if self.intent == "creator" else 0.03

        # Estado del agente
        self.used_free_trials = 0
        self.purchases = []
        self.total_spent_stars = 0
        self.total_spent_usd = 0.0
        self.shared_with_friends = 0

    def interact_with_bot(self):
        # 1. Prueba los servicios gratuitos
        # La mayoría prueba 1 a 3 servicios gratis
        trials_wanted = random.randint(1, 4) if self.intent == "casual" else random.randint(3, 8)
        self.used_free_trials = trials_wanted

        # 2. Reacción ante el límite de cuota (cuando se agota el gratis del servicio que necesita)
        # Si tiene necesidad continua:
        needs_more = True if (self.intent in ["creator", "student_office"] or random.random() < 0.35) else False

        if needs_more:
            if self.willingness_to_pay == 1:
                # Elige entre Pack 3 ($0.99 / 50 Stars) o Pack 10 ($2.99 / 150 Stars)
                choice = random.choices(["pack_3", "pack_10"], weights=[65, 35])[0]
                if choice == "pack_3":
                    self.purchases.append("pack_3")
                    self.total_spent_stars += 50
                    self.total_spent_usd += 0.99
                else:
                    self.purchases.append("pack_10")
                    self.total_spent_stars += 150
                    self.total_spent_usd += 2.99
            elif self.willingness_to_pay == 2:
                # Compra VIP ($9.99 / 500 Stars)
                self.purchases.append("pack_vip")
                self.total_spent_stars += 500
                self.total_spent_usd += 9.99

        # 3. Viralidad orgánica
        if random.random() < self.viral_share_rate:
            self.shared_with_friends = random.randint(1, 4)

def run_swarm_simulation(num_agents=10000):
    agents = [SyntheticUserAgent(i) for i in range(num_agents)]
    for a in agents:
        a.interact_with_bot()

    total_paying_users = sum(1 for a in agents if len(a.purchases) > 0)
    conversion_rate = (total_paying_users / num_agents) * 100

    pack_3_count = sum(a.purchases.count("pack_3") for a in agents)
    pack_10_count = sum(a.purchases.count("pack_10") for a in agents)
    vip_count = sum(a.purchases.count("pack_vip") for a in agents)

    total_stars = sum(a.total_spent_stars for a in agents)
    total_usd = sum(a.total_spent_usd for a in agents)
    total_viral_invites = sum(a.shared_with_friends for a in agents)

    # Fragment Payout (estimado ~$0.013 a $0.015 por Star)
    net_payout_usd = total_stars * 0.0135

    report = {
        "num_agents": num_agents,
        "total_paying_users": total_paying_users,
        "conversion_rate_pct": round(conversion_rate, 2),
        "sales_pack_3_usd_0_99": pack_3_count,
        "sales_pack_10_usd_2_99": pack_10_count,
        "sales_vip_usd_9_99": vip_count,
        "gross_stars_earned": total_stars,
        "gross_usd_value": round(total_usd, 2),
        "net_fragment_payout_usd": round(net_payout_usd, 2),
        "arpu_all_users_usd": round(total_usd / num_agents, 3),
        "arpu_paying_users_usd": round(total_usd / total_paying_users if total_paying_users else 0, 2),
        "viral_invites_generated": total_viral_invites,
        "effective_k_factor": round(total_viral_invites / num_agents, 3)
    }
    return report

if __name__ == "__main__":
    rep = run_swarm_simulation(10000)
    print(json.dumps(rep, indent=2))
