from __future__ import annotations
import random
import math
import os
from psychopy import visual, core, event, gui, data
from psychopy.visual.dot import DotStim
from itertools import permutations
from serial import Serial
from numpy import ones

# Settings
settings: dict = {
    "background_color": "grey",
    "EEG_connected": False,
    "EEG_port": None
}

EEG_codes = {
    #              | start (0)  | stim1 (1)  | stim2 (2)  | resp (3)   | end (4)
    # FIX      (1) |     10     |            |            |            |
    # OET      (2) |     20     |     21     |     22     |     23     |     24
    # MET      (3) |     30     |     31     |     32     |     33     |     34
    # RDM      (4) |     40     |           41            |     43     |     44
    # RSopen   (5) |     50     |            |            |            |     54
    # RSclosed (6) |     60     |            |            |            |     64

    "fix_cross": 10,
    "blockOET": 20,
    "OET1": 21,
    "OET2": 22,
    "responseOET": 23,
    "endBlockOET": 24,
    "blockMET": 30,
    "MET1": 31,
    "MET2": 32,
    "responseMET": 33,
    "endBlockMET": 34,
    "blockRDM": 40,
    "RDM": 41,
    "responseRDM": 43,
    "endBlockRDM": 44,
    "startRSopen": 50,
    "endRSopen": 54,
    "startRSclosed": 60,
    "endRSclosed": 64
}

def init_hardware(monitor_name: str, save_data: dict, visual_degrees: float|int):
    if monitor_name == "Lab":
        SCREEN_RES = (1920, 1080) # pix
        SCREEN_WIDTH = 54.5 # cm
        VIEW_DIST = 100 # cm
        refresh_rate = 100 # frames per second
    elif monitor_name == "Jelle1":
        SCREEN_RES = (1920, 1080)
        SCREEN_WIDTH = 34
        VIEW_DIST = 50
        refresh_rate = 144
    elif monitor_name == "Jelle2":
        SCREEN_RES = (1920, 1080)
        SCREEN_WIDTH = 60
        VIEW_DIST = 50
        refresh_rate = 120
    elif monitor_name == "Jelle3":
        SCREEN_RES = (1920, 1080)
        SCREEN_WIDTH = 53
        VIEW_DIST = 60
        refresh_rate = 200
    else:
        raise ValueError(f"SCREEN {monitor_name} does not exist")

    pix_per_deg = (SCREEN_RES[0] / SCREEN_WIDTH) / (2 * math.degrees(math.atan(0.5 / VIEW_DIST)))
    grid_size: float | int = pix_per_deg * visual_degrees
    save_data["ISI_in_frames"] = int((save_data["ISI"] / 1000) * refresh_rate)
        # this will be give inevitable rounding errors on devices with refresh rates not divisible by 100

    win = visual.Window(fullscr=True, units="pix", color=settings["background_color"])
    win.mouseVisible = False

    mouse = event.Mouse(win=win)
    clock = core.Clock()

    return win, refresh_rate, mouse, clock

def connect_EEG(port_name: str) -> bool:
    try:
        settings["EEG_port"] = Serial(port_name, baudrate=115200)
        settings["EEG_connected"] = True
        print(f"EEG port connected ({port_name}).")
        return True
    except Exception as e:
        print(f"EEG port not found: running without triggers. ({e})")
        return False

def EEG_trigger(trigger_code: str) -> None:
    if settings["EEG_connected"]:
        settings["EEG_port"].write(EEG_codes[trigger_code].to_bytes(1, 'big'))

def participant_info(save_dir: str, calibration: bool=False) -> dict:
    info = {
        "Participant nummer": "",
        "PC": ["Lab", "Jelle1", "Jelle2", "Jelle3"]
    } if calibration else {
        "Leeftijd": "",
        "Gender": ["Vrouw", "Man", "X"],
        "Participant nummer": "",
        "ISI": "",
        "PC": ["Lab", "Jelle1", "Jelle2", "Jelle3"]
    }
    info_box = gui.DlgFromDict(
        dictionary=info,
        title="Info participant",
        order= ["Participant nummer", "PC"] if calibration else ["Leeftijd", "Gender", "Participant nummer", "ISI", "PC"]
    )
    # Close experiment if "cancel" was pressed
    if not info_box.OK:
        core.quit()
    # Close experiment if nr was already used
    assert not os.path.exists(f"{save_dir}/data_{str(info['Participant nummer'])}.csv"), f"Number {info['Participant nummer']} is already in use."

    return {
        "nr": int(info["Participant nummer"]),  # noqa
        "PC": info["PC"]
    } if calibration else {
        "nr": int(info["Participant nummer"]),  # noqa
        "ISI": int(info["ISI"]),  # noqa
        "age": info["Leeftijd"],
        "gender": info["Gender"],
        "PC": info["PC"]
    }


def add_participant_data(trials: data.TrialHandler, participant_data: dict) -> None:
    for name, value in participant_data.items():
        trials.addData(name, value)


class RDM(DotStim):
    # decide also staircase procedure here? either contrast or amount of dots
    def __init__(self, class_settings: dict):
        self.win = class_settings["win"]
        self.FPS = class_settings["FPS"]
        self.color = class_settings["RDM_color"]

        DotStim.__init__(
            self,
            win=self.win,
            nDots=100,
            units="pix",
            dotSize=5,
            fieldShape="square",
            fieldSize=(settings["grid_size"], settings["grid_size"]),
            speed=(1 / self.FPS) * 50,  # pixels per frame #todo this is not right
            color=self.color,
            dotLife=int((1 / self.FPS) * 0.3),  # 0 to dotLife in frames
            coherence=0.55, # decide on this (maybe this is part of staircase? or maybe its contrast)
        )
        # Movement directions
        self.dir = -1
        self.dirs = [0, 180]
        self.dir_to_angle = {
            "right": 0,
            "left": 180
        }

        self.fix_cross = visual.ShapeStim(self.win, vertices=((0, -20), (0, 20), (0, 0), (-20, 0), (20, 0)), lineWidth=2.3,
                                          closeShape=False, lineColor=class_settings["color_gray"])
        self.clock = class_settings["clock"]

    def make_trials(self, n_trials: int) -> list:
        trial_list = []
        for _ in range(n_trials):
            trial_list.append(
                {
                    "type": "RDM",
                    "dir": random.choice(self.dirs) # decide fully random too?
                }
            )

        return trial_list

    def evaluation(self, rotation: int, response: str) -> int:
        return int(self.dir_to_angle[response] == rotation)

    def run(self, trials: data.TrialHandler, participant_data: dict, expHandler: data.ExperimentHandler) -> None:
        EEG_trigger("blockRDM")
        for trial in trials:
            # Prepare EEG trigger fixation cross
            self.win.callOnFlip(EEG_trigger, trigger_code="fix_cross")
            # Change direction of majority per trial
            self.dir = trial["dir"]
            # Fixation cross
            self.fix_cross.draw()
            self.win.flip()
            # Prepare EEG trigger when first trial frame presented
            self.win.callOnFlip(EEG_trigger, trigger_code="RDM")
            core.wait(random.randrange(500, 1500) / 1000)
            # Trial & response
            response = []
            event.clearEvents()
            first_cycle = True
            while not response:
                self.draw()
                self.win.flip()
                # Reset timer only after showing very first frame
                if first_cycle:
                    self.clock.reset()
                    first_cycle = False
                response = event.getKeys(keyList=["left", "right"])

            rt = self.clock.getTime()
            EEG_trigger("responseRDM")
            self.win.flip()

            trials.addData("rt", rt)
            trials.addData("response", self.dir_to_angle[response[0]])
            trials.addData("correct_response", trial["dir"])
            trials.addData("accuracy", self.evaluation(self.dir, response[0]))
            add_participant_data(trials, participant_data)
            expHandler.nextEntry()

        EEG_trigger("endBlockRDM")


class OET_MET:
    def __init__(self, class_settings: dict):
        self.win = class_settings["win"]
        self.clock = class_settings["clock"]
        self.mouse = class_settings["mouse"]
        self.ISI = class_settings["ISI"]
        self.color = class_settings["color_gray"]
        # Fix cross
        self.fix_cross = visual.ShapeStim(self.win, vertices=((0, -20), (0, 20), (0, 0), (-20, 0), (20, 0)), lineWidth=2.3,
                                          closeShape=False, lineColor=self.color)
        # Grid
        self.n_squares = 4
        self.grid_size: float | int = settings["grid_size"]
        self.grid_positions = self.calc_grid_positions(self.grid_size)
        self.grid = self.create_grid()
        # Annuli stim
        self.annuli_positions = self.calc_annuli_positions(self.grid_size)
        self.annulus = self.create_annulus_shape()
        # response boxes
        self.response_boxes = self.create_response_boxes()

    def calc_grid_positions(self, grid_size: float | int) -> list:
        spacing = grid_size / self.n_squares
        return [spacing * (i - self.n_squares / 2) for i in range(self.n_squares + 1)][::-1]

    def create_grid(self) -> visual.ElementArrayStim:
        length = settings["grid_size"]
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
            colors=self.color,
            units="pix",
        )

    def calc_annuli_positions(self, grid_size: float | int) -> dict:
        cell_size = grid_size / self.n_squares
        positions = {}
        counter = 1
        for row in range(self.n_squares - 1, -1, -1):  # Top to bottom
            for col in range(self.n_squares):  # Left to right
                positions[counter] = (
                    -grid_size / 2 + (col + 0.5) * cell_size,
                    -grid_size / 2 + (row + 0.5) * cell_size
                )
                counter += 1

        return positions

    def create_annulus_shape(self) -> visual.GratingStim:
        # Size of stimulus: 0.5/0.875 visual angle (Wutz2016) of one cell in grid (/2 for diameter to radius)
        RADIUS: float | int = settings["grid_size"] / self.n_squares * (0.5/0.875) / 2 # decide how big stim, same as Wutz and Devolder?, if same visual angle than this is just 0.5°
        MASK_RES: int = 1024
        THICKNESS: float | int = 0.20
        GAP: float | int = 0.15  # Higher = bigger gap
        # Start with no mask, gradually add pixels to mask if in certain area (middle of circle and edges)
        mask = ones((MASK_RES, MASK_RES)) * -1  # noqa
        for row in range(MASK_RES):
            for col in range(MASK_RES):
                x = (col / (MASK_RES - 1)) * 2 - 1
                y = (row / (MASK_RES - 1)) * 2 - 1
                if 1 - THICKNESS <= math.sqrt(x ** 2 + y ** 2) <= 1.0 and y >= GAP:
                    mask[row, col] = 1  # noqa

        return visual.GratingStim(self.win, tex=None, mask=mask, size=(RADIUS * 2, RADIUS * 2), color='black',
                                  contrast=0.8, units="pix")

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

    def trial_maker(self, n_trials: int, trial_type: str) -> list:
        trial_list = []
        for _ in range(n_trials):
            # Pick 2 random targets and keep all other stimuli
            all_stimuli: list = [x for x in range(1, self.n_squares ** 2 + 1)]
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

    def create_response_boxes(self) -> list[visual.Rect]:
        boxes = []
        for i in range(1, self.n_squares ** 2 + 1):
            boxes.append(
                {
                    "box": visual.Rect(self.win, size=(self.grid_size / 4) * .8, color=None, units="pix"),
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
            if box["box"].contains(self.mouse):
                if self.mouse.getPressed()[0]:
                    return box["nr"]
                box["box"].fillColor = 0.4
            else:
                box["box"].fillColor = None

        self.draw_response_boxes()
        return 0

    def response_handler(self, trial: dict) -> tuple:
        # By design, the response boxes start at (0, 0), resulting in a flash of all the boxes since
        # they all overlap with the mouse, this is solved by drawing them before showing the mouse. Feel free to refactor.
        response = 0
        self.draw_response_boxes()
        self.grid.draw()
        self.mouse.clickReset()
        self.mouse.setPos((0, 0))
        self.win.mouseVisible = True
        self.win.flip()
        self.clock.reset()
        while not response:
            # Color square that is being hovered over
            response = self.hover_response_boxes()
            self.grid.draw()
            self.win.flip()

        rt = self.clock.getTime()
        EEG_trigger(f"response{trial['type']}")
        self.win.mouseVisible = False

        # Reset colors of response boxes, clear display
        for box in self.response_boxes:
            box["box"].fillColor = settings["background_color"]

        self.win.flip()

        # Evaluation
        correct_response = trial["half_target"] if trial["type"] == "OET" else trial["missing_target"]
        accuracy = response == correct_response
        return rt, response, correct_response, accuracy

    def run(self, trials: data.TrialHandler, participant_data: dict, expHandler: data.ExperimentHandler, calibration: bool=False) -> None:
        """
        Note that currently both parts of the grid are displayed for one frame. This corresponds to 10ms on a 100Hz
        screen, but a loop (as during ISI) should be added if you work with a monitor with a multiple of 100Hz
        """
        EEG_trigger(f"block{trials.trialList[0]['type']}")
        for trial in trials: # todo trial counter?, overarching trial counter!
            # Use randomized ISI in calibration phase, and set ISI in main experiment
            if calibration:
                ISI = trial["random_ISI"]
            else:
                ISI = self.ISI

            # Prepare EEG trigger fixation cross
            self.win.callOnFlip(EEG_trigger, trigger_code="fixCross")
            # ___ Fixation cross for 0.5s ___
            self.fix_cross.draw()
            self.win.flip()
            core.wait(0.5)

            # ___ Empty grid for 0.5 to 1.5s ___
            self.grid.draw()
            self.win.flip()
            # Prepare EEG trigger first frame
            self.win.callOnFlip(EEG_trigger, trigger_code=f"{trial['type']}1")
            core.wait(random.randrange(500, 1500) / 1000)

            # ___ First frame ___
            self.grid.draw()
            self.draw_annuli(1, trial)
            self.win.flip()
            # ___ ISI with empty grid ___
            for _ in range(ISI):
                # For-loop for frame perfect timing, this is more temporally accurate than core.wait()
                self.grid.draw()
                self.win.flip()

            # Prepare EEG trigger second frame
            self.win.callOnFlip(EEG_trigger, trigger_code=f"{trial['type']}2")
            # ___ Second frame ___
            self.grid.draw()
            self.draw_annuli(2, trial)
            self.win.flip()

            # Stop second frame, wait 0.5s before response
            self.grid.draw()
            self.win.flip()
            core.wait(0.5)

            # ___ Response ___
            rt, response, correct_response, accuracy = self.response_handler(trial)
            trials.addData("rt", rt)
            trials.addData("response", response)
            trials.addData("correct_response", correct_response)
            trials.addData("accuracy", int(accuracy))
            trials.addData("ISI", ISI)
            add_participant_data(trials, participant_data)
            expHandler.nextEntry()

        EEG_trigger(f"endBlock{trials.trialList[0]['type']}")
        # todo add staircase per so many trials, but not in calibration!!


class OET(OET_MET):
    def __init__(self, class_settings: dict):
        OET_MET.__init__(self, class_settings)

    def make_trials(self, n_trials: int) -> list:
        return self.trial_maker(n_trials, "OET")  # Pass to parent class with correct trial_type


class MET(OET_MET):
    def __init__(self, class_settings: dict):
        OET_MET.__init__(self, class_settings)

    def make_trials(self, n_trials: int) -> list:
        return self.trial_maker(n_trials, "MET")  # Pass to parent class with correct trial_type


class rsEEG:
    def __init__(self, class_settings: dict):
        self.win = class_settings["win"]
        self.fix_cross = visual.ShapeStim(
            self.win,
            vertices=((0, -20), (0, 20), (0, 0), (-20, 0), (20, 0)),
            lineWidth=2.3,
            closeShape=False,
            lineColor=class_settings["color_gray"]
        )

    @staticmethod
    def trial_maker(duration: int, trial_type: str) -> list:
        return [
            {
            "type": trial_type,
            "duration": duration,
            }
        ]

    def run(self, trials: data.TrialHandler, participant_data: dict, expHandler: data.ExperimentHandler) -> None:
        for trial in trials:
            EEG_trigger(f"startRS{trial['type']}")
            self.fix_cross.draw()
            self.win.flip()
            core.wait(trial["duration"])
            EEG_trigger(f"endRS{trial['type']}")

            add_participant_data(trials, participant_data) # decide how to inform them that closed is over?
            expHandler.nextEntry()


class RS_open(rsEEG):
    def __init__(self, class_settings: dict):
        rsEEG.__init__(self, class_settings) # decide: find theoretical justification for durations

    def make_trials(self, duration: int=1) -> list: #todo duration is somehow same in closed and open
        return self.trial_maker(duration, "open") # Pass to parent class with correct duration and trial_type


class RS_closed(rsEEG):
    def __init__(self, class_settings: dict):
        rsEEG.__init__(self, class_settings)

    def make_trials(self, duration: int=3) -> list:
        return self.trial_maker(duration, "closed") # Pass to parent class with correct duration and trial_type


class Communication:
    def __init__(self, win: visual.Window):
        self.win = win
        self.text = visual.TextStim(win, color="black") # decide color

    def talk(self, message: str, flip: bool=True) -> None:
        # todo type texts
        options = {
            "intro_calibration": "[placeholder_intro_calibration]\nDruk op spatie om verder te gaan.",
            "intro": "[placeholder_intro]\nDruk op spatie om verder te gaan.",
            "RS_open_short": "[placeholder_RS_open_short]\nDruk op spatie om verder te gaan.",
            "RS_closed_short": "[placeholder_RS_closed_short]\nDruk op spatie om verder te gaan.",
            "RDM_short": "[placeholder_RDM_short]\nDruk op spatie om verder te gaan.",
            "OET_calibration": "[placeholder_OET_calibration]\nDruk op spatie om verder te gaan.",
            "OET_short": "[placeholder_OET_short]\nDruk op spatie om verder te gaan.",
            "MET_calibration": "[placeholder_MET_calibration]\nDruk op spatie om verder te gaan.",
            "MET_short": "[placeholder_MET_short]\nDruk op spatie om verder te gaan.",
            "outro_calibration": "[placeholder_outro_calibration]\nDruk op spatie om verder te gaan.",
            "outro": "[placeholder_outro]\nDruk op spatie om verder te gaan.",
        }
        self.text.text = options[message]
        self.text.draw()
        if flip:
            self.win.flip()
            event.waitKeys(keyList=["space"])


def add_esc_to_quit(win: visual.Window):
    event.globalKeys.clear()
    event.globalKeys.add(key="escape", func=stop, func_kwargs={"win": win})

def stop(win: visual.Window) -> None:
    if settings["EEG_connected"]:
        settings["EEG_port"].close()
    win.close()
    core.quit()

def task_ordener(nr: int, blocks_per_task: int, save_data: dict, tasks, calibration: bool=False) -> tuple:
    task_perms = list(permutations(tasks))
    nr_mod: int = int(nr % len(task_perms) + 1)
    task_order = (
        RS_open,
        RS_closed,
        *[clss for _ in range(blocks_per_task) for clss in task_perms[(nr_mod - 1) % len(task_perms)]],
        RS_open,
        RS_closed
    ) if not calibration else (
        *[clss for _ in range(blocks_per_task) for clss in task_perms[(nr_mod - 1) % len(task_perms)]],
    )
    # Save order to datafile
    save_data["task_order"] = (nr_mod, [clss.__name__ for clss in task_order])

    return task_order

def experiment_settings(clock: core.Clock, win: visual.Window, mouse: event.Mouse, save_data: dict, FPS, calibration: bool=False) -> dict:
    return {
        "clock": clock,
        "win": win,
        "mouse": mouse,
        "ISI": -1 if calibration else save_data["ISI_in_frames"],
        "color_gray": -0.2,
        "RDM_color": 0.4,
        "FPS": FPS
    }


def main(n_trials_per_block: int, blocks_per_task: int, visual_degrees: float|int) -> None:
    # Save file directory
    directory = os.path.join(os.getcwd(), "main_data")

    # Settings
    save_data = participant_info(directory)
    save_data["EEG_connected"] = connect_EEG("COM4")
    win, refresh_rate, mouse, clock = init_hardware(save_data["PC"], save_data, visual_degrees)
    comms = Communication(win) #todo place somewhere else

    # Add escape key to quit experiment
    add_esc_to_quit(win)

    # Save data
    expHandler = data.ExperimentHandler(dataFileName=f"{directory}/data_{str(save_data['nr'])}")

    ## Generate trial order based on participant number
    task_order = task_ordener(save_data["nr"], blocks_per_task, save_data, tasks=(MET, OET, RDM))
    exp_settings = experiment_settings(clock, win, mouse, save_data, refresh_rate)
    comms.talk("intro")

    # Run all blocks and their trials
    for task in task_order:
        # todo add intro
        # todo add task reminder (above grid)

        # Init task
        task = task(exp_settings)
        comms.talk(f"{type(task).__name__}_short")
        # Create trials and run them
        trials = data.TrialHandler(task.make_trials(n_trials_per_block if type(task).__name__ not in ("RSopen", "RSclosed") else {}), nReps=1, method="sequential")
        expHandler.addLoop(trials)
        task.run(trials, save_data, expHandler)

    comms.talk("outro")
    stop(win)

if __name__ == "__main__":
    main(
        n_trials_per_block=4,
        blocks_per_task=2,
        visual_degrees=2.5 # decide
    )
