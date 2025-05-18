import numpy as np

def generar_valor(dist, params):
    if dist == "uniform":
        return float(np.random.uniform(params["low"], params["high"]))
    elif dist == "normal":
        return float(np.random.normal(params["mu"], params["sigma"]))
    elif dist == "fixed":
        return float(params["value"]) if isinstance(params["value"], (int, float)) else params["value"]
    elif dist == "discrete":
        return float(np.random.choice(params["values"], p=params["probs"]))
    elif dist == "trunc_normal":
        return float(max(params.get("min", 0), np.random.normal(params["mu"], params["sigma"])))  # Paréntesis corregido aquí
    else:
        raise ValueError(f"Distribución '{dist}' no soportada.")

def generar_escenario(config):
    escenario = {}
    for var, dist_info in config["variables"].items():
        escenario[var] = generar_valor(dist_info["dist"], dist_info["params"])
    return escenario

def evaluar_formula(formula, variables):
    return eval(formula, {}, variables)