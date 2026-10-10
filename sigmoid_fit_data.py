import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plot
from scipy.optimize import minimize, brentq

# todo make this into pypalamedes
def sigmoid(ISI, b0, b1, lapse_rate):
    GUESSING_RATE = 1 / 16  # Theoretical lowest performance, purely based on guessing
    return GUESSING_RATE + (1 - GUESSING_RATE - lapse_rate) / (1 + np.exp(-(b0 + b1 * ISI)))

def neg_log_lik(params, ISI, accuracy):
    # Maximum likelihood estimation: -Σ [y·log(p) + (1-y)·log(1-p)]
    # p = prediction of accuracy
    p = np.clip(sigmoid(ISI, *params), 1e-9, 1 - 1e-9) # clip to prevent log(0)
    return -np.sum(accuracy * np.log(p) + (1 - accuracy) * np.log(1 - p))

def find_intersection_of_performances(file_dir: str, participant_nr: str):
    df = pd.read_csv(file_dir + participant_nr + ".csv")
    # Fit per taak via MLE op ruwe trials
    model_params = {}
    for task in ["MET", "OET"]:
        sub = df[df["type"] == task]
        fit = minimize(
            neg_log_lik,
            x0=[0, 0, 0], # No priors
            args=(
                sub["random_ISI"].to_numpy(),
                sub["accuracy"].to_numpy()
            ),
            bounds=[(-20, 20), (-5, 5), (0, 0.1)],
            method="L-BFGS-B", # Recommended for bounded parameters
        )
        model_params[task] = fit.x

        # Plot points
        means = sub.groupby("random_ISI")["accuracy"].mean().reset_index()  # means are only calculated to plot them
        plot.scatter(means["random_ISI"], means["accuracy"], label=f"{task} data")

    # Intersection MET/OET
    diff = lambda ISI: sigmoid(ISI, *model_params["MET"]) - sigmoid(ISI, *model_params["OET"])
    ISI_cross = None
    if diff(df["random_ISI"].min()) * diff(df["random_ISI"].max()) < 0:
        ISI_cross = brentq(diff, df["random_ISI"].min(), df["random_ISI"].max())

    # Plot
    x = np.linspace(df["random_ISI"].min(), df["random_ISI"].max(), 300)
    for task in ["MET", "OET"]:
        plot.plot(x, sigmoid(x, *model_params[task]), label=f"{task} fit")
    if ISI_cross:
        plot.axvline(ISI_cross, linestyle=":", color="black")

    plot.xlabel("ISI (frames)")
    plot.ylabel("% correct")
    if ISI_cross is not None:
        plot.title(f"Intersection = {round(ISI_cross)} frames (exact nr: {ISI_cross:.2f})")
    else:
        plot.title(f"No intersection found")
    plot.legend()

    if not os.path.exists("ISI_plots"):
        os.makedirs("ISI_plots")
    plot.savefig(f"ISI_plots/ISI_plot_{participant_nr}.png")

    if not os.path.exists("performance_intersections"):
        os.makedirs("performance_intersections")

    with open(f"performance_intersections/performance_intersection_{participant_nr}.txt", "w") as f:
        f.write(str(round(ISI_cross)) if ISI_cross is not None else "None")
    return round(ISI_cross) if ISI_cross is not None else "None"

if __name__ == "__main__":
    find_intersection_of_performances('calibration/calibration_', str(211))
