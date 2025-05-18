import numpy as np

def generar_valor(dist, params):
    if dist == "uniform":
        return np.random.uniform(params["low"], params["high"])
    elif dist == "normal":
        return np.random.normal(params["mu"], params["sigma"])
    else:
        raise ValueError(f"Distribución '{dist}' no soportada.")

def generar_escenario(config):
    escenario = {}
    for var, dist_info in config["variables"].items():
        escenario[var] = generar_valor(dist_info["dist"], dist_info["params"])
    return escenario

def evaluar_formula(formula, variables):
    return eval(formula, {}, variables)