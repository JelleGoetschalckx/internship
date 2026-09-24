import os
from psychopy import data
from main_internship_jelle import OET, MET, Communication, init_hardware, stop, participant_info, init_esc_to_quit, task_ordener, experiment_settings

def assign_random_ISI(trials: list, ISI_range: tuple) -> None:
    assert len(trials) >= ISI_range[-1] - ISI_range[0] + 1, f"Not enough trials ({len(trials)}) to test all ISI's ({ISI_range[-1]})."
    assert not (len(trials) % (ISI_range[-1] - ISI_range[0] + 1)), f"Calibration of ISI's ({ISI_range[0]} to {ISI_range[-1]}) is unbalanced with {len(trials)} trials."
    for i, trial in enumerate(trials):
        trial["random_ISI"] = int((i % (ISI_range[-1] - ISI_range[0] + 1)) + ISI_range[0])
        print(trial["random_ISI"])

def main_calibration(trials_per_block: int, blocks_per_task: int, ISI_range: tuple[int, int], visual_degrees: float|int) -> None:
    # Save file directory
    directory = os.path.join(os.getcwd(), "calibration_ISI")
    # Settings
    save_data = participant_info(directory, calibration=True)
    win, refresh_rate, mouse, clock, grid_size = init_hardware(save_data, visual_degrees, calibration=True)
    comms = Communication(win)
    init_esc_to_quit(win)

    # Save file
    expHandler = data.ExperimentHandler(dataFileName=f"{directory}/calibration_{str(save_data['nr'])}")

    # Generate practice and calibration trial order based on participant number
    task_order = task_ordener(save_data["nr"], blocks_per_task, save_data, tasks=(OET, MET), include_RS=False)
    exp_settings = experiment_settings(clock, win, mouse, save_data, refresh_rate, grid_size, calibration=True)
    comms.talk("intro_calibration")

    # Run all blocks and their trials
    for task in task_order: # todo add demo and practice trials for both blocks at very start
        # Init task
        task = task(exp_settings)
        comms.talk(f"{type(task).__name__}_calibration")
        # Create trials, assign a random ISI to them, run them in randomized order
        raw_trials = task.make_trials(trials_per_block)
        assign_random_ISI(raw_trials, ISI_range)
        trials = data.TrialHandler(raw_trials, nReps=1, method="random")
        expHandler.addLoop(trials)
        task.run(trials, save_data, expHandler, calibration=True)

    comms.talk("outro_calibration")
    stop(win)

    # todo add practice and tutorial (images)
    # todo add feedback on practice

if __name__ == "__main__":
    main_calibration(
        trials_per_block=14, # should be a multiple of max_ISI # decide
        blocks_per_task=2, # decide
        ISI_range=(1, 7), # decide (currently same as Devolder)
        visual_degrees=2.5 # decide
    )
