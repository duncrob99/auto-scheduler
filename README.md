# auto-scheduler

## Usage
The heart of the program is the to-do list, which is in the file `one_off_tasks`. Each new-line is a task, with each task being in the
format `<title>; <hrs until completion>; [<start date>-]<due date>`. In order to then use the program, simply run `python auto-scheduler.py`.
You will then be provided with some options. If you are figuring out what needs done tomorrow, most likely late in the day when
all work is done, select `y` for include today; otherwise, if you need to know what needs done today, select `n` (default is `y`). If you wish to be
assigned work on weekends, select `y` for include weekends (default is `y`). Particularly if the output is likely to be long, it is recommended to 
select `y` for reversing output, which will print later dates first, resulting in the most immediate tasks being the most
immediately visible (default is `y`). In addition, you can choose to separate the output frozm any previous commands by 5 blank lines in order to 
make it easier to see the beginning of the output (default is `y`).
