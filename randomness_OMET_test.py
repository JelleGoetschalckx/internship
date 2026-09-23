import random

def trial_maker(total_n_trials: int, trial_type: str) -> list:
    trial_list = []
    for _ in range(total_n_trials):
        # Pick 2 random targets and keep all other stimuli
        all_stimuli: list = [x for x in range(1, 16 + 1)]
        random.shuffle(all_stimuli)
        half_target: int = all_stimuli.pop(all_stimuli.index(random.choice(all_stimuli)))
        missing_target: int = all_stimuli.pop(
            all_stimuli.index(random.choice([x for x in all_stimuli if x != half_target])))
        # Place trial per trial into list
        trial_list.append(
            {
                "type": trial_type,
                "half_target": half_target,
                "missing_target": missing_target,
                "non_targets": all_stimuli,
                "rotation": random.choices([0, 45, 90, 135], k=len(all_stimuli)),
                "rotation_first_half_target": random.choice([0, 45, 90, 135, 180, 225, 270, 315, 360])
            }
        )

    return trial_list

n_trials = 2000
for i in range(50):
    trials = trial_maker(n_trials, "test")

    missing_counter = {}
    for trial in trials:
        if trial["missing_target"] not in missing_counter:
            missing_counter[trial["missing_target"]] = 1
        else:
            missing_counter[trial["missing_target"]] += 1
    print(missing_counter)


    import matplotlib.pyplot as plt
    plt.bar(range(len(missing_counter)), list(missing_counter.values()), align='center')
    plt.xticks(range(len(missing_counter)), list(sorted(missing_counter.keys())))
    plt.axhline(n_trials/16, linestyle=':', color='purple')
    plt.show()
