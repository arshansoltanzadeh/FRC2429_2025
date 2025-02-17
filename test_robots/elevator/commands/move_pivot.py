import commands2
from wpilib import SmartDashboard
from subsystems.pivot import Pivot
from wpimath.units import inchesToMeters, radiansToDegrees, degreesToRadians


class MovePivot(commands2.Command):  # change the name for your command

    def __init__(self, container, pivot:Pivot, mode='absoltue', indent=0) -> None:
        super().__init__()
        self.setName('Move Pivot')  # change this to something appropriate for this command
        self.indent = indent
        self.container = container
        self.pivot = pivot
        self.mode = mode
        # self.addRequirements(self.container.)  # commandsv2 version of requirements
        SmartDashboard.putNumber('pivot_cmd_goal_deg', 90)  # initialize the key we will use to run this command
        SmartDashboard.putString('pivot_cmd_mode', 'absolute')

    def initialize(self) -> None:
        """Called just before this Command runs the first time."""
        self.start_time = round(self.container.get_enabled_time(), 2)

        self.goal = SmartDashboard.getNumber('pivot_cmd_goal_deg', 90)  # get the elevator sp from the dash
        self.mode = SmartDashboard.getString('pivot_cmd_mode', 'absolute')

        if self.mode == 'absolute':
            self.pivot.set_goal(degreesToRadians(self.goal))
        else:
            self.pivot.move_degrees(delta_degrees=self.goal)

        print(f"{self.indent * '    '}** Started {self.getName()} with mode {self.mode} and goal {self.goal:.2f} at {self.start_time} s **", flush=True)

    def execute(self) -> None:
        pass

    def isFinished(self) -> bool:
        return True

    def end(self, interrupted: bool) -> None:
        end_time = self.container.get_enabled_time()
        message = 'Interrupted' if interrupted else 'Ended'
        print_end_message = False
        if print_end_message:
            print(f"{self.indent * '    '}** {message} {self.getName()} at {end_time:.1f} s after {end_time - self.start_time:.1f} s **")
            SmartDashboard.putString(f"alert",
                                     f"** {message} {self.getName()} at {end_time:.1f} s after {end_time - self.start_time:.1f} s **")
