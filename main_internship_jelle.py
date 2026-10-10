import random
import math
import os
from psychopy import visual, core, event, gui, data
from itertools import permutations
from serial import Serial
from numpy import ones, mean

"""
While our research only used the calibration phase, this code can easily be adapted to feature a main experiment 
as done in e.g., Wutz et al. (2018). Additional tasks can also be implemented into the main experiment loop.

Code written by Jelle Goetschalckx, partially based on code by Kirsten Devolder.
"""

def participant_info() -> tuple:
    info = {
        "Leeftijd": "",
        "Gender": ["Vrouw", "Man", "X"],
        "Participant nummer": "",
        "PC": ["Lab", "Jelle1", "Jelle2", "Jelle3"]
    }
    info_box = gui.DlgFromDict(
        dictionary=info,
        title="Info participant",
        order=["Leeftijd", "Gender", "Participant nummer", "ISI (in frames)", "PC"]
    )
    # Close experiment if "cancel" was pressed
    if not info_box.OK:
        core.quit()
    # Close experiment if nr was already used
    assert not os.path.exists(
        f"calibration_ISI/calibration_{info['Participant nummer']}.csv"), f"Number {info['Participant nummer']} is already in use."

    return int(info["Participant nummer"]), info["PC"], info["Leeftijd"], info["Gender"]  # noqa

def connect_EEG(port_name: str) -> tuple:
    try:
        print(f"EEG port connected ({port_name}).")
        return True, Serial(port_name, baudrate=115200)
    except Exception as e:
        print(f"EEG port not found: running without triggers. ({e})")
        return False, None

def add_participant_data(trials: data.TrialHandler, participant_data: dict) -> None:
        for name, value in participant_data.items():
            trials.addData(name, value)

def assign_random_ISI(trials: list, ISI_range: tuple) -> None:
    n_ISIs = ISI_range[-1] - ISI_range[0] + 1
    assert len(trials) >= n_ISIs, f"Not enough trials ({len(trials)}) to test all ISI's ({n_ISIs})."
    assert not (len(trials) % n_ISIs), f"Calibration of ISI's ({ISI_range[0]} to {ISI_range[-1]}) is unbalanced with {len(trials)} trials."
    for i, trial in enumerate(trials):
        trial["random_ISI"] = int((i % n_ISIs) + ISI_range[0])

def is_calibration(ISI):
    return isinstance(ISI, tuple)


class Experiment:
    def __init__(self, used_tasks: tuple, visual_degrees: int|float=3.5, EEG_port_name: str="COM4"):
        # Tasks and visuals
        self.used_tasks = used_tasks
        self.visual_degrees = visual_degrees
        self.grid_color = -0.2

        # Demographics and pc settings
        self.nr, self.pc, self.age, self.gender = participant_info()
        self.win, self.refresh_rate, self.mouse, self.clock, self.grid_size = self.init_hardware()

        # Text messages to participant
        self.comms = Communication(self.win)

        # EEG connection
        self.EEG_connected, self.EEG_port = connect_EEG(EEG_port_name)
        self.EEG_codes = {
            #              | start (0)  | stim1 (1)  | stim2 (2)  | resp (3)   | end (9)
            # FIX      (1) |     10     |            |            |            |
            # OET      (2) |     20     |     21   (212)   22     |     23     |     29
            # MET      (3) |     30     |     31   (312)   32     |     33     |     39
            # RSopen   (4) |     40     |            |            |            |     49
            # RSclosed (5) |     50     |            |            |            |     59

            "start_trial": 10,
            "blockOET": 20,
            "OET1": 21,
            "OET2": 22,
            "OET12": 212,
            "responseOET": 23,
            "endBlockOET": 29,
            "blockMET": 30,
            "MET1": 31,
            "MET2": 32,
            "MET12": 312,
            "responseMET": 33,
            "endBlockMET": 39,
            "startRSopen": 40,
            "endRSopen": 49,
            "startRSclosed": 50,
            "endRSclosed": 59
        }

        # Save data
        self.save_dir = os.getcwd()
        self.expHandler: data.ExperimentHandler
        self.expHandler_calibration = data.ExperimentHandler(dataFileName=f"{self.save_dir}/calibration/calibration_{str(self.nr)}")
        self.expHandler_main = data.ExperimentHandler(dataFileName=f"{self.save_dir}/main_data/data_{str(self.nr)}")
        # Save performance for calibrated experiment
        self.performance_OET_MET = []

        # Fixation cross
        self.fix_cross = visual.ElementArrayStim(
            self.win,
            nElements=2,
            xys=((0, 0), (0, 0)),
            sizes=((40, 1), (1, 40)),
            elementTex=None,
            elementMask=None,
            colors=((self.grid_color, self.grid_color, self.grid_color + 1), (self.grid_color, self.grid_color, self.grid_color + 1)),
            units="pix"
        )

    def get_screen_config(self) -> tuple:
        """
        :return: Screen resolution (pix), screen width (cm), view distance (cm), refresh rate (Hz)
        """
        match self.pc:
            case "Lab":
                return (1920, 1080), 54.5, 100, 100
            case "Jelle1":
                return (1920, 1080), 34, 50, 60
            case "Jelle2":
                return (1920, 1080), 60, 50, 120
            case "Jelle3":
                return (1920, 1080), 53, 60, 200
            case _:
                raise ValueError(f"SCREEN {self.pc} does not exist")

    def init_hardware(self):
        # Get screen specs
        screen_res, screen_width, view_dist, refresh_rate = self.get_screen_config()
        # Calculate size of grid
        pix_per_deg = (screen_res[0] / screen_width) / (2 * math.degrees(math.atan(0.5 / view_dist)))
        grid_size: float | int = pix_per_deg * self.visual_degrees #todo does not display correctly!!

        win = visual.Window(fullscr=True, units="pix")
        mouse = event.Mouse(win)
        clock = core.Clock()
        return win, refresh_rate, mouse, clock, grid_size

    def EEG_trigger(self, trigger_code: str) -> None:
        if self.EEG_connected:
            self.EEG_port.write(self.EEG_codes[trigger_code].to_bytes(1, 'big'))

    def init_esc_to_quit(self) -> None:
        event.globalKeys.clear()
        event.globalKeys.add(
            key="escape",
            func=self.stop,
            func_kwargs={"early_quit": True, "expHandler": self.expHandler, "participant_nr": self.nr}
        )

    def stop(self, early_quit=False, expHandler=None, participant_nr=0) -> None:
        if self.EEG_connected:
            self.EEG_port.close()
        if early_quit and expHandler is not None:
            if not os.path.exists(os.path.join(os.getcwd(), "early_quit")):
                os.mkdir(os.path.join(os.getcwd(), "early_quit"))
            expHandler.saveAsWideText(os.path.join(os.getcwd(), "early_quit", f"early_quit_{participant_nr}.csv"))
        self.win.close()
        core.quit()

    def task_ordener(self, n_blocks_per_task: int, tasks: tuple, RS_before: bool, RS_after: bool, RS_open_dur: int, RS_closed_dur: int) -> tuple:
        task_perms = list(permutations(tasks))
        nr_mod: int = int(self.nr % len(task_perms) + 1)
        task_order = (
            *((RS_open,) if RS_open_dur and RS_before else ()),
            *((RS_closed,) if RS_closed_dur and RS_before else ()),
            *[clss for _ in range(n_blocks_per_task) for clss in task_perms[(nr_mod - 1) % len(task_perms)]],
            *((RS_open,) if RS_open_dur and RS_after else ()),
            *((RS_closed,) if RS_closed_dur and RS_after else ()),
        )
        return nr_mod, task_order, [type(clss).__name__ for clss in task_order]


    def main(self, n_blocks_per_task: int, n_trials_per_block:int, RS_before: bool, RS_after: bool, RS_open_dur: int, RS_closed_dur: int, ISI: int|tuple) -> None:
        calibration: bool = is_calibration(ISI)
        self.comms.talk(f"intro{'_calibration' if calibration else ''}")

        ## Generate trial order based on participant number
        permutation_nr, tasks, task_order = self.task_ordener(n_blocks_per_task, self.used_tasks, RS_before, RS_after, RS_open_dur, RS_closed_dur)

        self.expHandler = self.expHandler_calibration if calibration else self.expHandler_calibration
        # Add escape key to quit experiment
        self.init_esc_to_quit()

        # Run all blocks and their trials
        task_complete_counter = 0
        self.performance_OET_MET = [] # this is only necessary for the main/calibrated experiment
        self.win.mouseVisible = False
        for task in tasks:
            task = task(self)
            task_name = type(task).__name__

            # Create trials and run them
            match task_name:
                case "RS_open":
                    arg = RS_open_dur
                    comm_arg = ""
                case "RS_closed":
                    arg = RS_closed_dur
                    comm_arg = ""
                case "OET" | "MET":
                    arg = n_trials_per_block
                    comm_arg = "_calibration" if calibration else ""
                case _:
                    raise ValueError(f"Experiment \"{task_name}\" does not exist")

            # Intro to task
            self.comms.talk(f"{task_name + comm_arg}")

            created_trials = task.make_trials(arg)
            if task_name not in ("RS_open", "RS_closed") and isinstance(ISI, tuple): # explicitly test again to make IDE happy
                assign_random_ISI(created_trials, ISI)
            trials = data.TrialHandler(created_trials, nReps=1, method="sequential" if not calibration else "random")
            self.expHandler.addLoop(trials)
            performance = task.run(
                trials=trials,
                expHandler=self.expHandler,
                participant_data={
                    "nr": self.nr,
                    "pc": self.pc,
                    "calibration": calibration,
                    "task_permutation": permutation_nr,
                    "task_order": task_order,
                    "EEG_connected": self.EEG_connected
                },
                ISI=ISI
            )
            if task_name in ("OET", "MET"):
                if not calibration:
                    self.performance_OET_MET.append(performance)
                task_complete_counter += 1
                self.comms.talk(
                    message="break",
                    progression=f"{task_complete_counter} van de {n_blocks_per_task * len(self.used_tasks)} blokken"
                )

        self.comms.talk(f"outro{'_calibration' if calibration else ''}")
        self.stop()


class OET_MET:
    def __init__(self, experiment: Experiment):
        self.experiment = experiment
        self.win = experiment.win

        # Task reminder above grid
        self.task_reminder = visual.TextStim(
            self.win,
            color='white',
            height=20,
            pos=(0, +175),
            autoLog=False
        )
        # Grid
        self.n_squares = 4

        self.grid_positions = self.calc_grid_positions()
        self.grid = self.create_grid()
        # Annuli stim
        self.annuli_positions = self.calc_annuli_positions()
        self.annulus = self.create_annulus_shape()
        # response boxes
        self.response_boxes = self.create_response_boxes()

    def calc_grid_positions(self,) -> list:
        spacing = self.experiment.grid_size / self.n_squares
        return [spacing * (i - self.n_squares / 2) for i in range(self.n_squares + 1)][::-1]

    def create_grid(self) -> visual.ElementArrayStim:
        length = self.experiment.grid_size
        line_width = 1
        coords = []
        sizes = []
        for ori in [0, 90]:
            for pos in self.grid_positions:
                coords.append((pos if ori else 0, 0 if ori else pos))
                sizes.append((line_width if ori else length, length if ori else line_width))

        return visual.ElementArrayStim(
            self.win,
            nElements=len(coords),
            xys=coords,
            sizes=sizes,
            elementTex=None,
            elementMask=None,
            colors=self.experiment.grid_color,
            units="pix",
        )

    def calc_annuli_positions(self) -> dict:
        cell_size = self.experiment.grid_size / self.n_squares
        positions = {}
        counter = 1
        for row in range(self.n_squares - 1, -1, -1):  # Top to bottom
            for col in range(self.n_squares):  # Left to right
                positions[counter] = (
                    -self.experiment.grid_size / 2 + (col + 0.5) * cell_size,
                    -self.experiment.grid_size / 2 + (row + 0.5) * cell_size
                )
                counter += 1

        return positions

    def create_annulus_shape(self) -> visual.GratingStim:
        # Size of stimulus: 0.5/0.875 visual angle (Wutz2018) of one cell in grid (/2 for diameter to radius)
        RADIUS: float | int = self.experiment.grid_size / self.n_squares * (0.5/0.875) / 2
        MASK_RES: int = 1024
        THICKNESS: float | int = 0.20
        GAP: float | int = 0.15  # Higher = bigger gap
        # Start with no mask, gradually add pixels to mask if in certain area (middle of circle and edges)
        mask = ones((MASK_RES, MASK_RES)) * -1
        for row in range(MASK_RES):
            for col in range(MASK_RES):
                x = (col / (MASK_RES - 1)) * 2 - 1
                y = (row / (MASK_RES - 1)) * 2 - 1
                if 1 - THICKNESS <= math.sqrt(x ** 2 + y ** 2) <= 1.0 and y >= GAP:
                    mask[row, col] = 1

        return visual.GratingStim(
            self.win,
            tex=None,
            mask=mask,
            size=(RADIUS * 2, RADIUS * 2),
            color='black',
            contrast=0.625,
            units="pix"
        )

    def draw_annuli(self, n_frame: int, trial: dict) -> None:
        # Pick only relevant positions for this frame (half of total)
        total_cells = len(trial["non_targets"])
        relevant_cells = trial["non_targets"][
            None if n_frame == 1 else total_cells // 2: total_cells // 2 if n_frame == 1 else None]
        for i, stim in enumerate(relevant_cells):
            for ori in [0, 180]:
                self.annulus.ori = trial["rotation"][i] + ori
                self.annulus.pos = self.annuli_positions[stim]
                self.annulus.draw()
        # Half annulus
        self.annulus.pos = self.annuli_positions[trial["half_target"]]
        self.annulus.ori = trial["rotation_first_half_target"] + (180 if n_frame == 2 else 0)
        self.annulus.draw()

    def find_pseudorandom_positions(self, n_trials: int):
        total_squares = self.n_squares ** 2
        assert n_trials % total_squares == 0, f"Not enough trials ({n_trials}) for a balanced pseudorandom design."

        list1 = [x for x in range(1, total_squares + 1)] * (n_trials // total_squares)
        list2 = list1[:]
        random.shuffle(list1)
        random.shuffle(list2)

        for i in range(len(list1)):
            # If identical element found at same index
            if list2[i] == list1[i]:
                solved = False
                # Iterate through the list until a valid swap partner is found
                candidate_i = 0
                while candidate_i < len(list1) and not solved:
                    if not solved and candidate_i != i and list2[candidate_i] != list1[i] and list2[i] != list1[
                        candidate_i]:
                        # Swap eligible partners
                        list2[i], list2[candidate_i] = list2[candidate_i], list2[i]
                        solved = True
                    candidate_i += 1
                # If somehow no solution was found, restart
                if not solved:
                    return self.find_pseudorandom_positions(n_trials)
        return list1, list2

    def trial_maker(self, n_trials: int, trial_type: str) -> list:
        half_targets, missing_targets = self.find_pseudorandom_positions(n_trials)
        trial_list = []
        for i in range(n_trials):
            # Place trial per trial into list
            half_target = half_targets[i]
            missing_target = missing_targets[i]
            non_targets = [x for x in range(1, self.n_squares ** 2 + 1) if x not in (half_target, missing_target)]
            trial_list.append(
                {
                    "type": trial_type,
                    "half_target": half_target ,
                    "missing_target": missing_target,
                    "non_targets": non_targets,
                    "rotation": random.choices([0, 45, 90, 135], k=self.n_squares ** 2),
                    "rotation_first_half_target": random.choice([0, 45, 90, 135, 180, 225, 270, 315, 360])
                }
            )
        return trial_list

    def create_response_boxes(self) -> list[visual.Rect]:
        boxes = []
        for i in range(1, self.n_squares ** 2 + 1):
            boxes.append(
                {
                    "box": visual.Rect(self.win, size=(self.experiment.grid_size / 4) * .8, color=None, units="pix"),
                    "nr": int(i),
                    "pos": self.annuli_positions[i]
                }
            )
        return boxes

    def draw_response_boxes(self) -> None:
        for box in self.response_boxes:
            box["box"].pos = box["pos"]
            box["box"].draw()

    def hover_response_boxes(self) -> int:
        for box in self.response_boxes:
            if box["box"].contains(self.experiment.mouse):
                if self.experiment.mouse.getPressed()[0]:
                    return box["nr"]
                box["box"].fillColor = 0.4
            else:
                box["box"].fillColor = None

        self.draw_response_boxes()
        return 0

    def response_handler(self, trial: dict, reminder_text: str) -> tuple:
        # By design, the response boxes start at (0, 0), resulting in a flash of all the boxes since
        # they all overlap with the mouse, this is solved by drawing them before showing the mouse. Feel free to refactor.
        response = 0
        self.draw_response_boxes()
        self.grid.draw()
        self.experiment.mouse.clickReset()
        self.experiment.mouse.setPos((0, 0))
        self.win.mouseVisible = True
        self.win.flip()
        self.experiment.clock.reset()
        while not response:
            # Color square that is being hovered over
            response = self.hover_response_boxes()
            self.grid.draw()
            self.reminder(reminder_text)
            self.win.flip()

        rt = self.experiment.clock.getTime()
        self.experiment.EEG_trigger(f"response{trial['type']}")
        self.win.mouseVisible = False
        # Reset colors of response boxes, clear display
        for box in self.response_boxes:
            box["box"].fillColor = self.win.color
        # Evaluation
        correct_response = trial["half_target"] if trial["type"] == "OET" else trial["missing_target"]
        accuracy = response == correct_response
        return rt, response, correct_response, accuracy

    def performance_staircase(self):
        mean_performance = mean(self.experiment.performance_OET_MET[-2:])
        if mean_performance > 0.6:
            self.annulus.contrast = max(0.25, self.annulus.contrast - 1/8)
        elif mean_performance < 0.4:
            self.annulus.contrast = min(1, self.annulus.contrast + 1/8)

    def reminder(self, reminder_text):
        self.task_reminder.text = reminder_text
        self.task_reminder.draw()

    def run(self, trials: data.TrialHandler, expHandler: data.ExperimentHandler, participant_data: dict, ISI: int|tuple) -> float | int:
        """
        Note that currently both parts of the grid are displayed for one frame. This corresponds to 10ms on a 100Hz
        screen, but a loop (as during ISI) should be added if you work with a monitor with a multiple of 100Hz
        """
        trial_counter = 0
        n_correct_this_block = 0
        reminder_text = "LEEG" if trials.trialList[0].type == "MET" else "HALF"
        # Change contrast of stimuli to get stable performance every two blocks (only in main experiment)
        if not is_calibration(ISI):
            if len(self.experiment.performance_OET_MET) and not len(self.experiment.performance_OET_MET) % 2:
                self.performance_staircase()
        # Run trials
        self.experiment.EEG_trigger(f"block{trials.trialList[0]['type']}")
        for trial in trials:
            # Use randomized ISI in calibration phase, and calibrated ISI in main experiment
            if isinstance(ISI, tuple): # explicitly test to make IDE happy
                current_ISI: int = trial["random_ISI"]
            else:
                current_ISI: int = ISI

            # Prepare EEG trigger start trial
            self.win.callOnFlip(self.experiment.EEG_trigger, trigger_code="start_trial")
            # ___ Empty grid for 1 to 2s ___
            self.grid.draw()
            self.experiment.fix_cross.draw()
            self.reminder(reminder_text)
            self.win.flip()
            # Prepare EEG trigger first frame
            self.win.callOnFlip(self.experiment.EEG_trigger, trigger_code=trial['type'] + "1" if current_ISI != -1 else "12")
            core.wait(random.randrange(1000, 2000 + 1)/1000)

            if current_ISI == -1:
                self.grid.draw()
                self.experiment.fix_cross.draw()
                self.draw_annuli(1, trial)
                self.draw_annuli(2, trial)
                self.reminder(reminder_text)
                self.win.flip() # display for one frame, send EEG trigger
            else:
                # ___ First frame ___
                self.grid.draw()
                self.experiment.fix_cross.draw()
                self.draw_annuli(1, trial)
                self.reminder(reminder_text)
                self.win.flip() # sends EEG trigger
                # ___ ISI with empty grid ___
                for _ in range(current_ISI):
                    # For-loop for frame-perfect timing, this is more accurate than core.wait()
                    self.grid.draw()
                    self.experiment.fix_cross.draw()
                    self.reminder(reminder_text)
                    self.win.flip()

                # Prepare EEG trigger second frame
                self.win.callOnFlip(self.experiment.EEG_trigger, trigger_code=f"{trial['type']}2")
                # ___ Second frame ___
                self.grid.draw()
                self.experiment.fix_cross.draw()
                self.draw_annuli(2, trial)
                self.reminder(reminder_text)
                self.win.flip() # sends EEG trigger

            # Show empty grid, wait 0.5s before response
            self.grid.draw()
            self.experiment.fix_cross.draw()
            self.reminder(reminder_text)
            self.win.flip()
            core.wait(0.5)
            # ___ Response ___
            rt, response, correct_response, accuracy = self.response_handler(trial, reminder_text)
            if accuracy:
                n_correct_this_block += 1
            # Save data
            trials.addData("rt", rt)
            trials.addData("response", response)
            trials.addData("correct_response", correct_response)
            trials.addData("accuracy", int(accuracy))
            trials.addData("ISI", ISI)
            trials.addData("n_trial_this_block", trial_counter)
            trials.addData("current_contrast", self.annulus.contrast)
            add_participant_data(trials, participant_data)
            expHandler.nextEntry()
            trial_counter +=1

        self.experiment.EEG_trigger(f"endBlock{trials.trialList[0]['type']}")
        return n_correct_this_block / len(trials.trialList)


class OET(OET_MET):
    def __init__(self, experiment: Experiment):
        OET_MET.__init__(self, experiment)

    def make_trials(self, n_trials: int) -> list:
        return self.trial_maker(n_trials, "OET")  # Pass to parent class with correct trial_type


class MET(OET_MET):
    def __init__(self, experiment: Experiment):
        OET_MET.__init__(self, experiment)

    def make_trials(self, n_trials: int) -> list:
        return self.trial_maker(n_trials, "MET")  # Pass to parent class with correct trial_type


class rsEEG:
    def __init__(self, experiment: Experiment):
        self.experiment = experiment

    @staticmethod
    def trial_maker(duration: int, trial_type: str) -> list:
        return [
            {
            "type": trial_type,
            "duration": duration,
            }
        ]

    def run(self, trials: data.TrialHandler, expHandler: data.ExperimentHandler, participant_data: dict, ISI) -> None:
        for trial in trials:
            self.experiment.EEG_trigger(f"startRS{trial['type']}")
            self.experiment.fix_cross.draw()
            self.experiment.win.flip()
            core.wait(trial["duration"])
            self.experiment.EEG_trigger(f"endRS{trial['type']}")

            add_participant_data(trials, participant_data)
            expHandler.nextEntry()


class RS_open(rsEEG):
    def __init__(self, experiment: Experiment):
        rsEEG.__init__(self, experiment) # decide: find theoretical justification for durations

    def make_trials(self, duration: int=1) -> list:
        return self.trial_maker(duration, "open") # Pass to parent class with correct duration and trial_type


class RS_closed(rsEEG):
    def __init__(self, experiment: Experiment):
        rsEEG.__init__(self, experiment)

    def make_trials(self, duration: int=3) -> list:
        return self.trial_maker(duration, "closed") # Pass to parent class with correct duration and trial_type


class Communication:
    def __init__(self, win: visual.Window):
        self.win = win
        self.text = visual.TextStim(win, color="white", height=35)

    def talk(self, message: str, progression: str="", flip: bool=True) -> None:
        # todo add demo text and practice text + feedback
        options = {
            "intro_calibration": "Welkom bij dit experiment!\n\nDruk op spatie om te starten.",
            "intro": "[placeholder_intro]",
            "RS_open": "Zodra zie je een kruis op het scherm, ontspan en kijk hier naar tot het weggaat.\n\nDruk op spatie om verder te gaan.",
            "RS_closed": "Zodra moet je je ogen even sluiten, ontspan en wacht tot je een signaal hoort.\n\nSluit je ogen en druk op spatie om verder te gaan.",
            "OET_calibration": "In het komende blok is het je taak om het vak met HALVE cirkels aan te duiden.\n\nDruk op spatie om te starten.",
            "OET": "[placeholder_OET_main]",
            "MET_calibration": "In het komende blok is het je taak om het LEGE vak aan te duiden.\n\nDruk op spatie om te starten.",
            "MET": "[placeholder_MET_main]",
            "break": f"Tijd voor een pauze. Je hebt {progression} voltooid.\n\nJe mag voorzichtig wat bewegen, let wel "
                     f"op voor de kabels. Leg je hoofd terug op de hoofdsteun als je klaar bent voor het volgende deel, "
                     f"druk op spatie om verder te gaan.",
            "outro_calibration": "Je hebt het einde van het experiment bereikt. Bedankt om deel te nemen!\n\nDruk op spatie om af te sluiten, en geef ons een seintje.",
            "outro": "[placeholder_outro_main]"
        }
        self.text.text = options[message]
        self.text.draw()
        if flip:
            self.win.flip()
            event.waitKeys(keyList=["space"])

if __name__ == "__main__":
    """
    Other valid total_n_blocks and total_n_trials to balance ISIs and pseudorandomize target locations:
    total_n_blocks | total_n_trials | n_trials_per_block | estimated duration (min)
    2              | 864            | 432.0              | 43.2
    2              | 960            | 480.0              | 48.0
    2              | 1056           | 528.0              | 52.8
    2              | 1152           | 576.0              | 57.6
    4              | 960            | 240.0              | 48.0
    4              | 1152           | 288.0              | 57.6
    6              | 864            | 144.0              | 43.2
    6              | 1152           | 192.0              | 57.6
    8              | 1152           | 144.0              | 57.6
  - 10             | 960            | 96.0               | 48.0 -
    12             | 1152           | 96.0               | 57.6
    """
    total_n_trials = 12 * 2 * 40 # 960 (estimated time: 3s per trial, 3s * 960 = 2880s = 48 min; = 40 trials per ISI per task
    total_n_blocks = 10
    Experiment(
        used_tasks=(OET, MET)
    ).main(
        n_blocks_per_task=total_n_blocks//2,
        n_trials_per_block=total_n_trials//total_n_blocks, # must be divisible by amount of elements in calibration_range
        RS_before=True,
        RS_after=True,
        RS_open_dur=1, # in seconds
        RS_closed_dur=1, # in seconds
        ISI = (-1, 10)
    )
