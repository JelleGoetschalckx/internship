import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from scipy.optimize import curve_fit, brentq

# Data
df = pd.read_csv("calibration_ISI/simulated_calibration.csv")

# Sigmoid
def sigmoid(ISIs, b0, b1, lapse_rate):
    guessing_rate = 1 / 16
    return guessing_rate + (1 - guessing_rate - lapse_rate) / (1 + np.exp(-(b0 + b1 * ISIs)))
# Intersection of sigmoid functions is where difference is 0
def difference(ISI):
    return sigmoid(ISI, *model_params["MET"]) - sigmoid(ISI, *model_params["OET"])

# Fit sigmoid to both tasks
model_params = {}
for task in ["MET", "OET"]:
    acc_per_ISI = df[df["type"] == task].groupby("ISI")["accuracy"].mean().reset_index()

    model_params[task], _ = curve_fit(
        sigmoid,
        acc_per_ISI["ISI"],
        acc_per_ISI["accuracy"],
        bounds=([-20, -5, 0], [20, 5, 0.1]) # limits of parameters
    )

    plt.scatter(acc_per_ISI["ISI"], acc_per_ISI["accuracy"], label=f"{task}")

# Find ISI where OET and MET intersect
isi_cross = None
if difference(df["ISI"].min()) * difference(df["ISI"].max()) < 0:
    isi_cross = brentq(
        difference,
        df["ISI"].min(),
        df["ISI"].max(),
    )
    print(f"ISI = {isi_cross:.2f} frames")
else:
    print("No intersection found.")


# ___ Plot ___
x = np.linspace(df["ISI"].min(), df["ISI"].max(), 300) # Make smooth plot between ISIs

# Plot per task
plt.plot(x, sigmoid(x, *model_params["MET"]), label="MET fit")
plt.plot(x, sigmoid(x, *model_params["OET"]), label="OET fit")

# Plot intersection
if isi_cross is not None:
    plt.scatter(isi_cross, sigmoid(isi_cross, *model_params["MET"]), color="black", zorder=5)
    plt.axvline(isi_cross, linestyle=":")

# Labels
plt.xlabel("ISI (frames)")
plt.ylabel("% correct")
plt.legend()
plt.show()

print(f"Intersection = {isi_cross:.2f} frames")
