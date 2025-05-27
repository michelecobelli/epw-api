import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import fsolve
import matplotlib.ticker as ticker
import pandas as pd

# Constants
P = 1.01325  # bar (standard atmosphere)
R = 0.08314  # m³·bar/(K·mol)
Tref = 0.0   # °C

Mw = 18.015  # g/mol (water)
Ma = 28.97   # g/mol (dry air)

Cpair = 1.005    # kJ/kg·K
Cpvap = 1.912    # kJ/kg·K
Cpliq = 4.182    # kJ/kg·K
Hvap = 2500.9    # kJ/kg at Tref

def pSatW_(T):
    Tc = 647.096
    Pc = 220.640
    a = np.array([0.0, -7.85951783, 1.84408259, -11.7866497, 22.6807411, -15.9618719, 1.80122502])
    Tn = 273.16
    Pn = 0.00611657
    b = np.array([-13.928169, 34.707823])

    if T >= 0.01 and T <= 373.0:
        phi = 1.0 - (T + 273.15)/Tc
        return Pc*np.exp((Tc/(T + 273.15))*(a[1]*phi + a[2]*phi**1.5
            + a[3]*phi**3.0 + a[4]*phi**3.5 + a[5]*phi**4.0 + a[6]*phi**7.5))
    elif T < 0.01 and T >= -100.0:
        theta = (T+273.15)/Tn
        return Pn*np.exp(b[0]*(1 - theta**-1.5) + b[1]*(1 - theta**-1.25))
    else:
        return float('nan')

pSatW = np.vectorize(pSatW_)

def plot_psychrometric_chart_with_epw(epw_path, P=1.01325, wmax=0.030, tmin=0.0, tmax=50.0):
    df = pd.read_csv(epw_path, skiprows=8, header=None)
    city_name = pd.read_csv(epw_path, nrows=1, header=None).iloc[0, 1]
    fig = plt.figure(figsize=(12, 8))
    ax = plt.axes()
    ax.set_title(f'Psychrometric Chart for {city_name} at {P:.5f} bar')
    ax.set_xlabel('Dry Bulb Temperature [°C]')
    ax.set_ylabel('Humidity Ratio [kg water / kg dry air]')
    ax.grid(True)
    ax.set_xlim(tmin, tmax)
    ax.set_ylim(0, wmax)

    ax.xaxis.set_major_locator(ticker.MultipleLocator(10))
    ax.xaxis.set_minor_locator(ticker.MultipleLocator(1))
    ax.yaxis.set_major_locator(ticker.MultipleLocator(0.005))
    ax.yaxis.set_minor_locator(ticker.MultipleLocator(0.001))

    T = np.linspace(tmin, tmax, 200)
    w_saturation = (Mw/Ma)/(P/pSatW(T) - 1.0)
    ax.plot(T, w_saturation, 'r', label='Saturation Curve')

    for rh in np.linspace(0.1, 1.0, 10):
        with np.errstate(divide='ignore', invalid='ignore'):
            w = (Mw/Ma) * rh / (P/pSatW(T) - rh)
            w = np.clip(w, 0, wmax)
            w[~np.isfinite(w)] = np.nan
        ax.plot(T, w, 'r', linewidth=0.5, alpha=0.6)
        idx = int(len(T) * 0.75)
        ax.text(T[idx], w[idx], f"{int(rh*100)}%", color='r', fontsize=8, va='bottom')

    hmax = round(Cpair*(tmax-Tref) + wmax*(Hvap + Cpvap*(tmax-Tref)), -1)+10
    hmin = round(Cpair*(tmin-Tref), -1)-10
    for h in np.linspace(hmin, hmax, 10):
        def f(t): return (Mw/Ma)/(P/pSatW(t) - 1.0)
        def g(t): return (h - Cpair*(t - Tref))/(Hvap + Cpvap*(t - Tref))
        try:
            t0 = round((tmin + tmax)/2)
            t_start = fsolve(lambda t: f(t) - g(t), t0)[0]
            if not np.isfinite(t_start) or t_start < tmin or t_start > tmax:
                continue
            t = np.linspace(t_start, tmax, 100)
            w = (h - Cpair*(t - Tref)) / (Hvap + Cpvap*(t - Tref))
            w = np.clip(w, 0, wmax)
            ax.plot(t, w, 'k--', linewidth=0.8, alpha=0.7)
            ax.text(t[0], w[0], f"H={h:.0f}", fontsize=7, color='k', ha='right')
        except:
            continue

    for ts in np.linspace(tmin, tmax, int(tmax - tmin)):
        try:
            ws = (Mw/Ma)/(P/pSatW(ts) - 1.0)
            t = np.linspace(ts, tmax)
            num = Cpair*(ts - t) + ws*(Hvap + Cpvap*(ts - Tref) - Cpliq*(ts - Tref))
            den = Hvap + Cpvap*(t - Tref) - Cpliq*(ts - Tref)
            w = num / den
            w = np.clip(w, 0, wmax)
            ax.plot(t, w, 'b', alpha=0.3)
        except:
            continue

    # --- Plot EPW Data ---
    dry_bulb = df[6].astype(float)
    rel_hum = df[8].astype(float)
    RH_frac = rel_hum / 100
    w_points = np.array([
        (Mw / Ma) * rh / (P / pSatW(t) - rh)
        for t, rh in zip(dry_bulb, RH_frac)
    ])
    ax.scatter(dry_bulb, w_points, s=6, alpha=0.3, color='blue', label='EPW Hourly Data')

    # --- ASHRAE 55 Comfort Zone ---
    t_comfort = [20, 27]
    rh_bounds = [0.3, 0.7]
    rh_lines = np.linspace(rh_bounds[0], rh_bounds[1], 50)
    t_band = np.linspace(t_comfort[0], t_comfort[1], 50)
    for rh in [rh_bounds[0], rh_bounds[1]]:
        w = (Mw/Ma) * rh / (P / pSatW(t_band) - rh)
        ax.plot(t_band, w, color='green', linestyle='-', linewidth=1.5, alpha=0.7)
    for t in [t_comfort[0], t_comfort[1]]:
        w = (Mw/Ma) * rh_lines / (P / pSatW(t) - rh_lines)
        ax.plot([t]*len(w), w, color='green', linestyle='-', linewidth=1.5, alpha=0.7)
    ax.fill_between(t_band,
                    (Mw/Ma) * rh_bounds[0] / (P / pSatW(t_band) - rh_bounds[0]),
                    (Mw/Ma) * rh_bounds[1] / (P / pSatW(t_band) - rh_bounds[1]),
                    color='green', alpha=0.1, label='ASHRAE 55 Comfort Zone')

    ax.legend()
    plt.show()

    # 🖼 Convert to Base64 image string
    buf = BytesIO()
    plt.savefig(buf, format="png", bbox_inches='tight')
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("utf-8")