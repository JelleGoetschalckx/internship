import os
from psychopy import data
from main_internship_jelle import OET, MET, Communication, init_hardware, stop, participant_info, add_esc_to_quit, task_ordener, experiment_settings

def assign_random_ISI(trials: list, max_ISI: int) -> None:
    assert len(trials) >= max_ISI, f"Not enough trials ({len(trials)}) to test all ISI's ({max_ISI})."
    assert not (len(trials) % max_ISI), f"ISI's ({max_ISI}) are unbalanced with {len(trials)} trials."
    for i, trial in enumerate(trials):
        trial["random_ISI"] = int((i % max_ISI) + 1)

def main_calibration(trials_per_block: int, blocks_per_task: int, max_ISI) -> None:
    # Save file directory
    directory = os.path.join(os.getcwd(), "calibration_ISI")
    # Settings
    save_data = participant_info(directory, calibration=True)
    win, FPS, frame_duration, mouse, clock = init_hardware(save_data["PC"])
    comms = Communication(win)
    add_esc_to_quit(win)

    # Save file
    expHandler = data.ExperimentHandler(dataFileName=f"{directory}/calibration_{str(save_data['nr'])}")

    # Generate practice and calibration trial order based on participant number
    task_order = task_ordener(save_data["nr"], blocks_per_task, save_data, tasks=(OET, MET), calibration=True)
    exp_settings = experiment_settings(clock, win, mouse, save_data, FPS, calibration=True)
    comms.talk("intro_calibration")

    # Run all blocks and their trials
    for task in task_order: # todo add demo and practice trials for both blocks at very start
        # Init task
        task = task(exp_settings)
        comms.talk(f"{type(task).__name__}_calibration")
        # Create trials, assign a random ISI to them, run them in randomized order
        raw_trials = task.make_trials(trials_per_block)
        assign_random_ISI(raw_trials, max_ISI)
        trials = data.TrialHandler(raw_trials, nReps=1, method="random")
        expHandler.addLoop(trials)
        task.run(trials, save_data, expHandler, calibration=True)

    comms.talk("outro_calibration")
    stop(win)

    # todo add practice and tutorial (images)
    # todo add feedback on practice

if __name__ == "__main__":
    main_calibration(14, 2, 7)
