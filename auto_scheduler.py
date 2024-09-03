#!./.venv/bin/python3
import datetime
import io
import math
import os
import subprocess
from copy import deepcopy
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional

from colorama import Fore, Back, Style
from tqdm import tqdm

import sync

weekday_conversion = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}

time_inc = 1 / 60
day_start_time = datetime.time(5, 0, 0)


def round_hours_to_minute(time: float) -> float:
    return round(time * 60) / 60


def floor_hours_to_minute(time: float) -> float:
    return math.floor(time * 60) / 60


def ceil_hours_to_minute(time: float) -> float:
    return math.ceil(time * 60) / 60


def bool_input(query: str, default: bool = True) -> bool:
    query = query[0].upper() + query[1:]
    if default:
        option_string = '[Y/n]'
    else:
        option_string = '[y/N]'
    while True:
        input_str = input(f'{query}? {option_string}: ')
        if input_str in ['y', '']:
            return True
        elif input_str == "n":
            return False
        print('Invalid input, please try again')


def input_start_date() -> datetime.date:
    # Get date to start on (i.e. current day, tomorrow)
    initial_date = datetime.datetime.now().date()
    if datetime.datetime.now().time() < day_start_time:
        # Before day start time, so count as yesterday
        initial_date -= datetime.timedelta(days=1)
    include_today = bool_input('include today')
    if not include_today:
        initial_date += datetime.timedelta(days=1)
    return initial_date


def get_screen_width(default: int = 30) -> int:
    try:
        return int(os.popen('stty size', 'r').read().split()[1])
    except IndexError:
        return default


def separate_output() -> None:
    output = ''
    print(Back.GREEN)
    for j in range(get_screen_width()):
        output += ':'
    for i in range(20):
        print(output)
    print(Style.RESET_ALL)


def datetime_to_date_string(input_date: datetime.datetime.date) -> str:
    return str(input_date.day) + '/' + str(input_date.month) + '/' + str(input_date.year)[2:]


def date_string_to_datetime(input_date_string: str) -> datetime.date:
    split_string = input_date_string.split('/')
    try:
        local_day = int(split_string[0])
        month = int(split_string[1])
        year = int('20' + split_string[2])
        try:
            return datetime.date(year, month, local_day)
        except ValueError:
            print("Invalid date:", year, month, local_day)
    except IndexError:
        print("Invalid date-string:", input_date_string)


def decimal_to_timestring(value: float) -> str:
    hours = round(value - value % 1)
    minutes = round((value - hours) * 60)
    if minutes == 60:
        hours += 1
        minutes = 0

    if minutes >= 10:
        return str(hours) + ":" + str(minutes)
    else:
        return str(hours) + ":0" + str(minutes)


def timestring_to_decimal(timestring: str) -> float:
    split_time = timestring.split(':')
    hours = float(split_time[0])
    if len(split_time) > 1:
        minutes = float(split_time[1])
    else:
        minutes = 0

    decimal_time = hours + minutes / 60
    return decimal_time


def get_work_on_day(requested_day: datetime.date, weekly_work: Dict[str, float],
                    single_fixed_tasks: Dict[datetime.date, float]) -> float:
    weekday = weekday_conversion[requested_day.weekday()]
    regular_work = weekly_work[weekday]
    if requested_day in single_fixed_tasks:
        one_off_work = single_fixed_tasks[requested_day]
        total_work = regular_work + one_off_work
    else:
        total_work = regular_work

    return total_work


def load_fixed_tasks(filename: str = 'day_fixed_work.txt') -> Tuple[
        Dict[datetime.date, Dict[str, float]], Dict[str, float], Dict[datetime.date, float]]:
    day_fixed_work = io.open(filename)
    fixed_work_lines = day_fixed_work.readlines()
    # Bring fixed work data into memory structures
    tasks = {}
    one_off_working: Dict[datetime.date, float] = {}
    regular_working = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0,
                       'Sunday': 0}
    for day_info in fixed_work_lines:
        if day_info == '\n' or day_info[0] == '#':
            continue

        _split_info = day_info.split(';')
        day = _split_info[0]
        work_time = timestring_to_decimal(_split_info[1].split('\n')[0])
        if day in regular_working.keys():
            regular_working[day] += work_time
        elif date_string_to_datetime(day) in one_off_working.keys():
            one_off_working[date_string_to_datetime(day)] += work_time
        else:
            one_off_working[date_string_to_datetime(day)] = work_time

        # Deal with titled work data
        if len(_split_info) >= 3:
            work_title = _split_info[2].strip()
            if day in regular_working.keys():
                # TODO: Deal with regulars
                pass
            else:
                _date = date_string_to_datetime(day)
                if _date in tasks:
                    if work_title in tasks[_date]:
                        tasks[_date][work_title] += work_time
                    else:
                        tasks[_date][work_title] = work_time
                else:
                    tasks[_date] = {}
                    tasks[_date][work_title] = work_time

    return tasks, regular_working, one_off_working


@dataclass
class Task:
    title: str
    subtitle: str
    required_hours: float
    min_time: float
    start_date: datetime.date
    due_date: datetime.date
    actual_due_date: datetime.date


class DateOrderError(Exception):
    def __init__(self, task: Task, message="Incorrect Date Order"):
        self.task = task
        self.message = message
        super().__init__(message)


def load_flexi_tasks(cur_date: datetime.date, filename: str = 'one-off_tasks', weekends: bool = True) -> List[Task]:
    one_off_tasks = io.open(filename)
    one_off_tasks_lines = one_off_tasks.readlines()
    # Bring task list data into memory structures
    tasks = []
    due_dateless_task_indices = []
    for _index, _task in enumerate(one_off_tasks_lines):
        split_info = _task.split(';')

        if _task[0] == '#' or split_info == '\n' or '\n' in split_info:
            continue

        _title = split_info[0]
        try:
            _required_hours = timestring_to_decimal(split_info[1].split(' ')[1])
        except IndexError:
            print(split_info)
            continue

        _due_date = split_info[2].split(' ')[1].split('\n')[0]
        if len(split_info) >= 4:
            _min_time = timestring_to_decimal(split_info[3].split(' ')[1])
        else:
            _min_time = time_inc

        if _due_date == 'none':
            due_dateless_task_indices.append(_index)
            _start_date = max(date_string_to_datetime(_due_date[0]), cur_date)
            _due_date = date_string_to_datetime('1/1/01')
        elif len(_due_date.split('-')) > 1:
            _due_date = _due_date.split('-')
            _start_date = max(date_string_to_datetime(_due_date[0]), cur_date)
            _due_date = date_string_to_datetime(_due_date[1])
        else:
            _start_date = cur_date
            _due_date = date_string_to_datetime(_due_date)

        print(cur_date)
        _actual_due_date = _due_date
        _due_date = max(_due_date, cur_date + datetime.timedelta(days=1))
        if _due_date.weekday() in [6, 5] and not weekends:
            _due_date = _due_date - datetime.timedelta(days=_due_date.weekday() - 4)
            if _start_date > _due_date:
                _start_date = _due_date - datetime.timedelta(days=1)

        if len(split_info) >= 5:
            _subtitle = split_info[4]
        else:
            _subtitle = _title

        if _subtitle[0] == ' ':
            _subtitle = _subtitle[1:]

        if _subtitle[-1] == '\n':
            _subtitle = _subtitle[:-1]

        if _start_date >= _due_date:
            raise DateOrderError(Task(_title, _subtitle, _required_hours, _min_time, _start_date, _due_date, _actual_due_date))
        tasks.append(Task(_title, _subtitle, _required_hours, _min_time, _start_date, _due_date, _actual_due_date))

    # Set due date for any tasks without due date to maximum due date
    max_due_date = sorted(tasks, key=lambda x: x.due_date)[-1].due_date
    for _index in due_dateless_task_indices:
        tasks[_index].due_date = max_due_date

    # Sort tasks by due date
    tasks = sorted(sorted(tasks, key=lambda x: x.actual_due_date), key=lambda x: x.due_date)
    return tasks


def remove_fixed_from_flexi(fixed, flexi):
    # Remove set work from task requirements
    for _date in fixed:
        for _title in fixed[_date]:
            time_to_remove = fixed[_date][_title]
            for _task in flexi:
                if time_to_remove <= time_inc:
                    break
                elif _title == _task.subtitle:
                    _task.required_hours -= min(time_to_remove, _task.required_hours)
                    time_to_remove -= min(time_to_remove, _task.required_hours)


def calc_daily_work(_tasks: List[Task], regular_tasks: Dict[str, float], single_fixed_work: Dict[datetime.date, float],
                    include_weekends: bool) -> Tuple[Dict[datetime.date, float], Dict[datetime.date, float]]:
    # Work out how many hours to work a day
    _tasks = deepcopy(_tasks)
    regular_tasks = deepcopy(regular_tasks)
    single_fixed_work = deepcopy(single_fixed_work)

    include_weekends = deepcopy(include_weekends)
    _auto_work_per_day: Dict[datetime.date, float] = {}
    _work_on_days_to_due = {}
    for _index, _task in enumerate(tqdm(_tasks, desc='Calculating total hours')):
        _required_hours = _task.required_hours
        # Get list of days which could possibly be used
        _available_days = [_task.start_date + datetime.timedelta(days=x)
                           for x in range(0, (_task.due_date - _task.start_date).days)]

        # Get total work on each day and slate weekends for removal if necessary
        indices_to_delete = []
        for day_index, _date in enumerate(_available_days):
            if _date.weekday() in [6, 5] and not include_weekends:
                indices_to_delete.append(day_index)
                continue
            if _date in _auto_work_per_day:
                _work_on_days_to_due[_date] = get_work_on_day(_date, regular_tasks, single_fixed_work) + \
                                              _auto_work_per_day[_date]
            else:
                _work_on_days_to_due[_date] = get_work_on_day(_date, regular_tasks, single_fixed_work)

        # Can't delete while iterating over list, so actually remove weekends now
        for deletable_index in reversed(indices_to_delete):
            del _available_days[deletable_index]

        if len(_available_days) <= 0:
            _date = _task.due_date - datetime.timedelta(days=1)
            _available_days = [_date]
            if _date in _auto_work_per_day:
                _work_on_days_to_due[_date] = get_work_on_day(_date, regular_tasks, single_fixed_work) + \
                                              _auto_work_per_day[_date]
            else:
                _work_on_days_to_due[_date] = get_work_on_day(_date, regular_tasks, single_fixed_work)

        # Add hours to day with smallest amount of work so far
        iter = 0
        while _required_hours > 0 and len(_work_on_days_to_due) > 0:
            iter += 1
            time_sorted_work_amounts = sorted(_available_days, key=lambda x: _work_on_days_to_due[x])
            min_work_day = time_sorted_work_amounts[0]
            min_work_amount = _work_on_days_to_due[min_work_day]
            second_min_work_day: Optional[datetime.date] = None
            num_mins = 0
            for day in time_sorted_work_amounts:
                if round_hours_to_minute(_work_on_days_to_due[day] - _work_on_days_to_due[min_work_day]) >= time_inc:
                    second_min_work_day = day
                    break
                else:
                    num_mins += 1
            if second_min_work_day is not None:
                optimal_split = min(
                    max(min((_work_on_days_to_due[second_min_work_day] - _work_on_days_to_due[min_work_day]),
                            ceil_hours_to_minute(_required_hours / num_mins)), _task.min_time), _required_hours)
            else:
                optimal_split = min(max(floor_hours_to_minute(_required_hours / len(_available_days)), _task.min_time),
                                    _required_hours)
            # optimal_split = ceil_hours_to_minute(_required_hours / math.floor(_required_hours / optimal_split) - 1e-10)
            for day in time_sorted_work_amounts:
                if _work_on_days_to_due[day] > min_work_amount or _required_hours < optimal_split:
                    break
                else:
                    if day in _auto_work_per_day:
                        _auto_work_per_day[day] += optimal_split
                        _work_on_days_to_due[day] += optimal_split
                    elif day in _work_on_days_to_due:
                        _auto_work_per_day[day] = optimal_split
                        _work_on_days_to_due[day] += optimal_split
                    else:
                        _auto_work_per_day[day] = optimal_split
                        _work_on_days_to_due[day] += optimal_split
                    _required_hours = round_hours_to_minute(_required_hours - optimal_split)

    return _auto_work_per_day, _work_on_days_to_due


def calc_daily_subjects(tasks: List[Task], auto_work_per_day: Dict[datetime.date, float]) -> \
        Tuple[Dict[datetime.date, Dict[str, float]], float]:
    # Assign subjects to each day

    # Ensure mutable objects aren't mutated
    tasks = deepcopy(tasks)
    auto_work_per_day = deepcopy(auto_work_per_day)

    _daily_titles = {}
    warning_str = ''
    missed_time = 0
    for index, _task in enumerate(tqdm(tasks, desc='Assigning subjects')):
        available_days = [_task.start_date + datetime.timedelta(days=x) for x in
                          range(0, (_task.due_date - _task.start_date).days) if
                          _task.start_date + datetime.timedelta(days=x) in auto_work_per_day]

        _required_hours = _task.required_hours
        failed_min_time = 0
        while _required_hours >= time_inc and len(available_days) > 0:
            previous_hours = _required_hours
            work_to_add = max(round_hours_to_minute(_required_hours / len(available_days)), _task.min_time)
            for date in available_days:
                if _required_hours >= work_to_add and auto_work_per_day[date] >= work_to_add:
                    auto_work_per_day[date] = round_hours_to_minute(auto_work_per_day[date] - work_to_add)
                    _required_hours = round_hours_to_minute(_required_hours - work_to_add)
                    if date in _daily_titles:
                        if _task.title in _daily_titles[date]:
                            _daily_titles[date][_task.title] += work_to_add
                        else:
                            _daily_titles[date][_task.title] = work_to_add
                    else:
                        _daily_titles[date] = {_task.title: work_to_add}

            if previous_hours == _required_hours:
                if failed_min_time > 50:
                    warning_str += "Not enough time for " + _task.title + " (" + _task.subtitle + ") with " + \
                                   str(_required_hours) + " hour(s) extra.\n"
                    missed_time += _required_hours
                    break
                _task.min_time = time_inc
                assert len(available_days) > 0
                failed_min_time += 1
        if len(available_days) <= 0:
            if _required_hours > 1:
                warning_str += 'Do ' + str(_required_hours) + ' hours of ' + _task.subtitle + ' now!\n'
            else:
                warning_str += 'Do ' + str(_required_hours) + ' hour of ' + _task.subtitle + ' now!\n'
    print(warning_str)
    return _daily_titles, missed_time


def calc_daily_tasks(tasks: List[Task], subject_distribution: Dict[datetime.date, Dict[str, float]]) -> \
        Dict[datetime.date, Dict[str, int]]:
    # Assign specific tasks to dates
    tasks = deepcopy(tasks)
    subject_distribution = deepcopy(subject_distribution)
    _daily_subtitles = {}
    for task in tqdm(tasks, desc="Assigning tasks"):
        required_hours = task.required_hours
        for date in sorted(filter(lambda x: x >= task.start_date, subject_distribution)):
            if (task.title in subject_distribution[date] and required_hours > 0
                    and subject_distribution[date][task.title]) > 0:
                auto_work_to_add = min(required_hours, subject_distribution[date][task.title])
                required_hours -= auto_work_to_add
                subject_distribution[date][task.title] -= auto_work_to_add
                output_subtitle = task.subtitle
                overdue = task.due_date - task.actual_due_date

                # Ensure they close cleanly to zero
                if 0 < required_hours < time_inc:
                    print('Minimising ' + task.subtitle + ': required hours = ' + str(required_hours))
                    required_hours = 0
                if 0 < subject_distribution[date][task.title] < time_inc:
                    print('Minimising ' + task.subtitle + ': daily titles = ' +
                          str(subject_distribution[date][task.title]))
                    subject_distribution[date][task.title] = 0

                if required_hours <= 0:
                    output_subtitle = "(Complete) " + output_subtitle
                if overdue.days > 1:
                    output_subtitle = f'(OVERDUE {str(overdue.days - 1)} DAY{"S" if overdue.days > 2 else ""}) {output_subtitle}'
                elif overdue.days == 1:
                    output_subtitle = "(DUE TODAY) " + output_subtitle
                elif task.due_date == date + datetime.timedelta(days=1):
                    if task.due_date == datetime.datetime.now().date() + datetime.timedelta(days=1):
                        output_subtitle = "(DUE TOMORROW) " + output_subtitle
                    else:
                        output_subtitle = "(DUE NEXT DAY) " + output_subtitle
                if date in _daily_subtitles:
                    if output_subtitle in _daily_subtitles[date]:
                        _daily_subtitles[date][output_subtitle] += auto_work_to_add
                    else:
                        _daily_subtitles[date][output_subtitle] = auto_work_to_add
                else:
                    _daily_subtitles[date] = {output_subtitle: auto_work_to_add}
        if required_hours >= time_inc:
            print('%s: %s' % (task.subtitle, required_hours))
    return _daily_subtitles


def print_results(_daily_subtitles: Dict[datetime.date, Dict[str, int]],
                  _work_on_days_to_due: Dict[datetime.date, float],
                  weekly_work: Dict[str, float],
                  single_fixed_work: Dict[datetime.date, float]) -> None:
    # Display results
    screen_width = get_screen_width()
    actual_hours_sum = 0
    for _date in sorted(_daily_subtitles, reverse=reverse_output):
        total_auto = 0
        for _task in _daily_subtitles[_date]:
            total_auto += _daily_subtitles[_date][_task]

        # Create correct number of title dashes
        output = '{0} {1} ({2} auto/{3} total)'.format(weekday_conversion[_date.weekday()], str(_date),
                                                       decimal_to_timestring(total_auto),
                                                       decimal_to_timestring(_work_on_days_to_due[_date]))
        cur_side_left = True
        if len(output) >= screen_width:
            output = '-' * screen_width + '\n' + output + '\n' + '.' * screen_width
        while len(output) < screen_width:
            if cur_side_left:
                output = '-' + output
            else:
                output = output + '-'

            cur_side_left = not cur_side_left

        print(Fore.GREEN)
        print(output)
        print(Style.RESET_ALL)

        for _task in _daily_subtitles[_date]:
            print(_task + ': ' + decimal_to_timestring(_daily_subtitles[_date][_task]))
            actual_hours_sum += _daily_subtitles[_date][_task]

        # Show if there's a miss-match in work amounts
        excess_work = total_auto + get_work_on_day(_date, weekly_work, single_fixed_work) - _work_on_days_to_due[_date]
        if round_hours_to_minute(excess_work) > 0:
            print(Fore.RED + decimal_to_timestring(excess_work) + ' hours of extra work' + Style.RESET_ALL)
        elif round_hours_to_minute(excess_work) < 0:
            print(Fore.RED + 'Missing ' + decimal_to_timestring(-excess_work) + ' hours of work' + Style.RESET_ALL)


def all_calcs(flexi_tasks, regular_fixed, one_off_fixed, weekends):
    flexi_per_day, work_on_days_to_due = calc_daily_work(flexi_tasks, regular_fixed, one_off_fixed, weekends)
    daily_titles, _ = calc_daily_subjects(flexi_tasks, flexi_per_day)
    daily_subtitles = calc_daily_tasks(flexi_tasks, daily_titles)
    return daily_subtitles, work_on_days_to_due


if __name__ == '__main__':
    # Sync with Google Drive
    print("Updating data from drive")
    sync.safe_sync()

    # Input choices
    start_date = input_start_date()
    weekends = bool_input('include weekends')
    reverse_output = bool_input('reverse output')
    if bool_input('clear terminal history'):
        subprocess.call('reset')
    elif bool_input('separate output'):
        separate_output()

    # Load data
    fixed_tasks, regular_fixed, one_off_fixed = load_fixed_tasks()
    try:
        flexi_tasks = load_flexi_tasks(start_date)
    except DateOrderError as e:
        print(f"{e.task.title} - {e.task.subtitle} has a due date before the start date ({e.task.due_date} <= {e.task.start_date})")
        exit()
    remove_fixed_from_flexi(fixed_tasks, flexi_tasks)

    print("All input data imported")

    # Calculate task distribution
    result, work_on_days_to_due = all_calcs(flexi_tasks, regular_fixed, one_off_fixed, weekends)

    print_results(result, work_on_days_to_due, regular_fixed, one_off_fixed)
