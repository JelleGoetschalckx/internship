from __future__ import annotations
from psychopy import visual, core, event, gui, data
from psychopy.visual.dot import DotStim
from itertools import permutations
from serial import Serial
from numpy import ones
import random
import math
import os

# Settings
settings: dict = {
    "background_color": "grey",
    "N_CELLS": (4, 4),
    "MET/OET_FRAMES": 1,
    "TRIALS_PER_BLOCK": 45,
    "TOTAL_BLOCKS": 20,
    "VISUAL_ANGLE": 2.5,
    "EEG_connected": False,
    "EEG_port": None
}

EEG_codes = {
    """
                 | start (0)  | stim1 (1)  | stim2 (2)  | resp (3)   | end (4)
    FIX      (1) |     10     |            |            |            |
    OET      (2) |     20     |     21     |     22     |     23     |     24
    MET      (3) |     30     |     31     |     32     |     33     |     34
    RDM      (4) |     40     |           41            |     43     |     44
    RSopen   (5) |     50     |            |            |            |     54
    RSclosed (6) |     60     |            |            |            |     64
    
    """
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

def init_hardware(monitor_name: str):
    if monitor_name == "Lab":
        SCREEN_RES = (1920, 1080)  # screen resolution (pix)
        SCREEN_WIDTH = 53  # screen width (cm) #todo
        VIEW_DIST = 97  # viewing distance (cm) #todo
        FPS = 100
    elif monitor_name == "Jelle1":
        SCREEN_RES = (1920, 1080)  # screen resolution (pix)
        SCREEN_WIDTH = 34  # screen width (cm)
        VIEW_DIST = 50  # viewing distance (cm)
        FPS = 60
    elif monitor_name == "Jelle2":
        SCREEN_RES = (1920, 1080)  # screen resolution (pix)
        SCREEN_WIDTH = 60  # screen width (cm)
        VIEW_DIST = 50  # viewing distance (cm)
        FPS = 60
    elif monitor_name == "Jelle3":
        SCREEN_RES = (1920, 1080)
        SCREEN_WIDTH = 53
        VIEW_DIST = 60
        FPS = 200
    else:
        raise ValueError(f"SCREEN {monitor_name} does not exist")

    pix_per_deg = (SCREEN_RES[0] / SCREEN_WIDTH) / (2 * math.degrees(math.atan(0.5 / VIEW_DIST)))  # pixels per degree
    settings["pix_per_degree"] = pix_per_deg
    settings["grid_size"]: float|int = pix_per_deg * settings["VISUAL_ANGLE"]

    win = visual.Window(fullscr=True, units="pix", color=settings["background_color"])
    win.mouseVisible = False

    ms = win.getMsPerFrame(nFrames=100, showVisual=False)
    frame_duration = (ms[0] / 1000.0) if (ms and ms[0]) else (1 / 60)
    mouse = event.Mouse(win=win)
    clock = core.Clock()

    return win, FPS, frame_duration, mouse, clock

def connect_EEG(port_name: str) -> None:
    try:
        settings["port"] = Serial(port_name, baudrate=115200)
        settings["EEG_connected"] = True
        print(f"EEG port connected ({port_name}).")
    except Exception as e:
        print(f"EEG port not found: running without triggers. ({e})")

def EEG_trigger(trigger_code: str) -> None:
    """
    todo: threading.Timer(0.01, lambda: settings["EEG_port"].write(0.to_bytes(1, 'big'))).start()
        ! might not be safe to write from other tread to port made with one tread
        -> zet process op andere thread om timing niet in weg te staan
    """
    if settings["EEG_connected"]:
        settings["EEG_port"].write(EEG_codes[trigger_code].to_bytes(1, 'big'))
        core.wait(0.01)
        settings["EEG_port"].write((0).to_bytes(1, 'big'))

def participant_info() -> dict:
    """
    Makes a dialogue box to ask for participant info
    :return: participant number, age and gender
    """
    info = {
        "Leeftijd": "",
        "Gender": ["Vrouw", "Man", "X"],
        "Participant nummer": "",
        "ISI": "",
        "PC": ["Lab", "Jelle1", "Jelle2", "Jelle3"]
    }
    info_box = gui.DlgFromDict(
        dictionary=info,
        title="Info participant",
        order=["Leeftijd", "Gender", "Participant nummer", "ISI", "PC"]
    )
    # Close experiment if "cancel" was pressed
    if not info_box.OK:
        core.quit()

    return {
        "nr": int(info["Participant nummer"]), # noqa
        "ISI": int(info["ISI"]), # noqa
        "age": info["Leeftijd"],
        "gender": info["Gender"],
        "PC": info["PC"]
    }

def get_task_order(nr: int) -> tuple:
    """
    Generate task order based on nr
    :param nr: participant number
    :return: permutation number, full task order for current participant
    """
    task_perms = list(permutations(("MET", "OET", "RDM")))
    nr_mod = nr % len(task_perms) + 1
    return (
        nr_mod,
        [
            "eyes-open",
            "eyes-closed",
            *task_perms[(nr_mod - 1) % len(task_perms)],
            "eyes-open",
            "eyes-closed"
        ]
    )

def add_participant_data(trials: data.TrialHandler, participant_data: dict) -> None:
    for name, value in participant_data.items():
        trials.addData(name, value)


class RDM(DotStim):
    def __init__(self, win: visual.Window, clock: core.Clock, FPS: int, color: float|int=0.4):
        DotStim.__init__(
            self,
            win=win,
            nDots=100,
            units="pix",
            dotSize=5,
            fieldShape="square",
            fieldSize=(settings["grid_size"], settings["grid_size"]),
            speed=(1/FPS)*50,  # pixels per frame
            color=color,
            dotLife=int((1/FPS) * 0.3),  # 0 to dotLife in frames
            coherence=0.55,
        )
        # Movement directions
        self.dir = -1
        self.dirs = [0, 90, 180, 270]
        self.dir_to_angle = {
            "right": 0,
            "up": 90,
            "left": 180,
            "down": 270
        }  # !! degrees go counterclockwise

        self.fix_cross = visual.ShapeStim(win, vertices=((0, -20), (0, 20), (0, 0), (-20, 0), (20, 0)), lineWidth=2.3, closeShape=False, lineColor=color)
        self.clock = clock
        
    def trial_maker(self, n_trials: int) -> list:
        trial_list = []
        for _ in range(n_trials):
            trial_list.append(
                {
                    "type": "RDM",
                    "dir": random.choice(self.dirs)
                }
            )

        return trial_list

    def evaluation(self, rotation: int, response: str) -> int:
        accuracy = int(self.dir_to_angle[response] == rotation)
        return accuracy

    def run(self, trials: data.TrialHandler, participant_data: dict, exp_data: data.ExperimentHandler) -> None:
        EEG_trigger("blockRDM")
        for trial in trials:
            # Prepare EEG trigger fixation cross
            self.win.callOnFlip(EEG_trigger, trigger_code="fixCross")
            # Change direction of majority per trial
            self.dir = trial["dir"]
            # Fixation cross
            self.fix_cross.draw()
            self.win.flip()
            # Prepare EEG trigger when first trial frame presented
            self.win.callOnFlip(EEG_trigger, trigger_code="RDM")
            core.wait(random.randrange(500, 1500)/1000)
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
                response = event.getKeys(keyList=["left", "right", "up", "down"])

            EEG_trigger("responseRDM")
            rt = self.clock.getTime()
            self.win.flip()

            trials.addData("rt", rt)
            trials.addData("response", self.dir_to_angle[response[0]])
            trials.addData("correct_response", trial["dir"])
            trials.addData("accuracy", self.evaluation(self.dir, response[0]))
            add_participant_data(trials, participant_data)
            exp_data.nextEntry()

        EEG_trigger("endBlockRDM")

    def demo(self) -> None:
        raise NotImplementedError


class OET_MET:
    def __init__(self, win: visual.Window, clock: core.Clock, mouse: event.Mouse, ISI: int, color: float|int=-0.2):
        self.win = win
        self.clock = clock
        self.mouse = mouse
        self.ISI = ISI
        self.color = color
        # Fix cross
        self.fix_cross = visual.ShapeStim(win, vertices=((0, -20), (0, 20), (0, 0), (-20, 0), (20, 0)), lineWidth=2.3, closeShape=False, lineColor=color)
        # Grid
        self.n_grids = int(settings["N_CELLS"][0]) * int(settings["N_CELLS"][1])
        self.grid_size: float|int = settings["grid_size"]
        self.grid_positions = self.calc_grid_positions(self.grid_size)
        self.grid_line = visual.Line(win, units="pix", lineColor=color)
        self.grid = self.create_grid()
        # Annuli stim
        self.annuli_positions = self.calc_annuli_positions(self.grid_size)
        self.annulus = self.create_annulus_shape()
        # response boxes
        self.response_boxes = self.create_response_boxes()

    @staticmethod
    def calc_grid_positions(grid_size: float|int) -> list:
        n_squares = settings["N_CELLS"][0]
        return [
            grid_size + grid_size / 4 * i - (grid_size + grid_size / 4 * n_squares / 2) for i in range(n_squares + 1)
        ][::-1]

    def create_grid(self) -> visual.ElementArrayStim:
        length = settings["grid_size"]
        line_width = self.grid_line.lineWidth
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

    @staticmethod
    def calc_annuli_positions(grid_size: float|int) -> dict:
        n_rows = settings["N_CELLS"][0]
        n_cols = settings["N_CELLS"][1]
        cell_width = grid_size / n_rows
        cell_height = grid_size / n_cols

        positions = {}
        counter = 1
        for row in range(n_rows - 1, -1, -1): # Top to bottom
            for col in range(n_cols): # Left to right
                positions[counter] = (-grid_size / 2 + (col + 0.5) * cell_width, -grid_size / 2 + (row + 0.5) * cell_height)
                counter += 1

        return positions

    def create_annulus_shape(self) -> visual.GratingStim:
        # Size of stimulus: three quarters of one cell in grid
        RADIUS: float|int = settings["grid_size"] * (3 / 4) / 4 / 2
        MASK_RES: int = 1024
        THICKNESS: float|int = 0.20
        GAP: float|int = 0.15  # Higher = bigger gap
        # Start with no mask, gradually add pixels to mask if in certain area (middle of circle and edges)
        mask = ones((MASK_RES, MASK_RES)) * -1 # noqa
        for row in range(MASK_RES):
            for col in range(MASK_RES):
                x = (col / (MASK_RES - 1)) * 2 - 1
                y = (row / (MASK_RES - 1)) * 2 - 1
                if 1 - THICKNESS <= math.sqrt(x ** 2 + y ** 2) <= 1.0 and y >= GAP:
                    mask[row, col] = 1 # noqa

        return visual.GratingStim(self.win, tex=None, mask=mask, size=(RADIUS * 2, RADIUS * 2), color='black', contrast=0.8, units="pix")

    def draw_annuli(self, n_frame: int, trial: dict) -> None:
        # Pick only relevant positions for this frame (half of total)
        total_cells = len(trial["non_targets"])
        relevant_cells = trial["non_targets"][None if n_frame == 1 else total_cells // 2: total_cells // 2 if n_frame == 1 else None]
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
            all_stimuli: list = [x for x in range(1, self.n_grids + 1)]
            random.shuffle(all_stimuli)
            half_target: int = all_stimuli.pop(all_stimuli.index(random.choice(all_stimuli)))
            missing_target: int = all_stimuli.pop(all_stimuli.index(random.choice([x for x in all_stimuli if x != half_target])))
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
        for i in range(1, self.n_grids + 1):
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
        self.win.flip()
        self.mouse.setPos((0, 0))
        self.win.mouseVisible = True
        self.clock.reset()
        while not response:
            # Color square that is being hovered over
            response = self.hover_response_boxes()
            self.grid.draw()
            self.win.flip()

        EEG_trigger(f"response{trial['type']}")
        rt = self.clock.getTime()
        self.win.mouseVisible = False

        # Reset colors of response boxes, clear display
        for box in self.response_boxes:
            box["box"].fillColor = settings["background_color"]

        self.win.flip()

        # Evaluation
        correct_response = trial["half_target"] if trial["type"] == "OET" else trial["missing_target"]
        accuracy = response == correct_response
        return rt, response, correct_response, accuracy

    def run(self, trials: data.TrialHandler, participant_data: dict, exp_data: data.ExperimentHandler) -> None:
        EEG_trigger(f"block{trials.trialList[0]['type']}")
        for trial in trials:
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
            core.wait(random.randrange(500, 1500)/1000)

            # ___ First frame ___
            self.grid.draw()
            self.draw_annuli(1, trial)
            self.win.flip()

            # ___ ISI with empty grid ___ todo fix timing?? (maybe measures not reliable)
            for _ in range(self.ISI):
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
            trials.addData("ISI", self.ISI)
            add_participant_data(trials, participant_data)
            exp_data.nextEntry()

        EEG_trigger(f"endBlock{trials.trialList[0]['type']}")

    def demo(self):
        raise NotImplementedError


class OET(OET_MET):
    def __init__(self, win: visual.Window, clock: core.Clock, mouse: event.Mouse, ISI: int):
        OET_MET.__init__(self, win, clock, mouse, ISI)

    def make_trials(self, n_trials: int) -> list:
        return self.trial_maker(n_trials, "OET")  # Pass to parent class with correct trial_type


class MET(OET_MET):
    def __init__(self, win: visual.Window, clock: core.Clock, mouse: event.Mouse, ISI: int):
        OET_MET.__init__(self, win, clock, mouse, ISI)

    def make_trials(self, n_trials: int) -> list:
        return self.trial_maker(n_trials, "MET")  # Pass to parent class with correct trial_type


class rsEEG:
    def __init__(self, duration: int, clock: core.Clock):
        self.duration = duration
        self.clock = clock

    def run_rsEEG(self, RS_type):
        self.clock.reset()
        EEG_trigger(f"startRS{RS_type}")
        while self.clock.getTime() < self.duration:
            pass


class RS_open(rsEEG):
    def __init__(self, duration, clock):
        rsEEG.__init__(self, duration, clock)

    def run(self):
        rsEEG.run_rsEEG(self, "open")


class RS_closed(rsEEG):
    def __init__(self, duration, clock):
        rsEEG.__init__(self, duration, clock)

    def run(self):
        rsEEG.run_rsEEG(self, "closed")


def stop(win: visual.Window) -> None:
    if settings["EEG_connected"]:
        settings["EEG_port"].close()
    win.close()
    core.quit()

def main():
    # Settings
    demographics = participant_info()
    win, FPS, frame_duration, mouse, clock = init_hardware(demographics["PC"])
    demographics["ISI_in_frames"] = math.ceil((demographics["ISI"] / 1000 * FPS))
    # Connect EEG
    connect_EEG("COM4")
    demographics["EEG_connected"] = True

    # Escape key
    event.globalKeys.clear()
    event.globalKeys.add(key="escape", func=stop, func_kwargs={"win": win})

    # Save file
    full_directory = os.path.join(os.getcwd(), "internship_jelle")
    exp_data = data.ExperimentHandler(dataFileName=full_directory + "/" + str(demographics["nr"]))

    ## GENERATE TRIALS
    # Counterbalanced order of tasks, get personal order for participant
    task_order = get_task_order(demographics["nr"])
    demographics["task_order"] = task_order

    # RDM
    RDM_task = RDM(win, clock, FPS)
    RDM_trials = data.TrialHandler(RDM_task.trial_maker(5), nReps=1, method="sequential")
    exp_data.addLoop(RDM_trials)

    # OET
    OET_task = OET(win, clock, mouse, demographics["ISI_in_frames"])
    OET_trials = data.TrialHandler(OET_task.make_trials(5), nReps=1, method="sequential")
    exp_data.addLoop(OET_trials)

    # MET
    MET_task = MET(win, clock, mouse, demographics["ISI_in_frames"])
    MET_trials = data.TrialHandler(MET_task.make_trials(5), nReps=1, method="sequential")
    exp_data.addLoop(MET_trials)


    RDM_task.run(RDM_trials, demographics, exp_data)
    OET_task.run(OET_trials, demographics, exp_data)
    MET_task.run(MET_trials, demographics, exp_data)


    # TODO !! trials must be added in correct order for participant

    stop(win)

if __name__ == "__main__":
    main()
    # todo: device manager -> view -> show hidden devices -> check under 'ports' which port gets added
