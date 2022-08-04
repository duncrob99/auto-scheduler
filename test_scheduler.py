import datetime
import math
import sys
from io import StringIO
from math import ceil
from typing import List, Dict

from hypothesis import example, assume, settings, Verbosity, given, note, strategies as st

import auto_scheduler
from auto_scheduler import Task, DateOrderError

shared_due_date = st.shared(st.dates(min_value=datetime.date(2021, 1, 2), max_value=datetime.date(2025, 12, 31)))
shared_min_time = st.shared(st.builds(lambda mins: mins / 60, st.integers(min_value=ceil(auto_scheduler.time_inc * 60),
                                                                          max_value=24 * 60)))


@st.composite
def earlier_dates(draw):
    return draw(
        st.dates(min_value=datetime.date(2021, 1, 1), max_value=draw(shared_due_date) - datetime.timedelta(days=1)))


@st.composite
def earlier_dates_incl(draw):
    return draw(st.dates(min_value=datetime.date(2021, 1, 1), max_value=draw(shared_due_date)))


shared_start_date = st.shared(earlier_dates())


@st.composite
def required_time_strat(draw):
    return draw(st.builds(lambda mins: mins / 60, st.integers(
        min_value=ceil(draw(shared_min_time) * 60),
        max_value=(draw(shared_due_date) - draw(shared_start_date)).days * 24 * 60)))


safe_floats = st.floats(allow_nan=False, allow_infinity=False)
safe_dates = st.dates(min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2099, 12, 31))
early_dates = st.dates(min_value=datetime.date(2021, 1, 1), max_value=datetime.date(2000, 12, 31))
pos_floats = st.floats(allow_nan=False, allow_infinity=False, min_value=0)
sensible_floats = st.floats(allow_nan=False, allow_infinity=False, min_value=0, max_value=24)
sensible_times = st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=24 * 60))
pos_float_times = st.builds(lambda mins: mins / 60, st.integers(min_value=1, max_value=24 * 60))
sensible_strings = st.text(st.characters(whitelist_categories=['L', 'N']), max_size=3)
task_strategy = st.builds(auto_scheduler.Task, sensible_strings, sensible_strings, required_time_strat(),
                          shared_min_time,
                          shared_start_date, shared_due_date, earlier_dates_incl())


@given(safe_dates)
def test_invert_datetime_to_date(date):
    datestring = auto_scheduler.datetime_to_date_string(date)
    assert auto_scheduler.date_string_to_datetime(datestring) == date


@given(st.floats(allow_infinity=False, allow_nan=False))
def test_invert_decimal_to_timestring(decimal):
    timestring = auto_scheduler.decimal_to_timestring(decimal)
    assert abs(auto_scheduler.timestring_to_decimal(timestring) - decimal) < auto_scheduler.time_inc


weekly_mapping = {'Monday': sensible_times,
                  'Tuesday': sensible_times,
                  'Wednesday': sensible_times,
                  'Thursday': sensible_times,
                  'Friday': sensible_times,
                  'Saturday': sensible_times,
                  'Sunday': sensible_times}
small_weekly_mapping = {'Monday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17)),
                        'Tuesday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17)),
                        'Wednesday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17)),
                        'Thursday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17)),
                        'Friday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17)),
                        'Saturday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17)),
                        'Sunday': st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=17))}
weekdays = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


@given(safe_dates,
       st.fixed_dictionaries(weekly_mapping),
       st.dictionaries(st.dates(), sensible_times))
@settings(verbosity=Verbosity.verbose)
def test_getting_work(requested_day, weekly_work, single_fixed_work):
    weekday = weekdays[requested_day.weekday()]
    answer = (weekly_work[weekday] if weekday in weekly_work else 0) + (
        single_fixed_work[requested_day] if requested_day in single_fixed_work else 0)
    assert auto_scheduler.get_work_on_day(requested_day, weekly_work, single_fixed_work) == answer


# Include actual values
start_date = datetime.date.today()
fixed_tasks, regular_fixed, one_off_fixed = auto_scheduler.load_fixed_tasks()
try:
    flexi_tasks = auto_scheduler.load_flexi_tasks(start_date)
except DateOrderError as e:
    print("Flexi tasks has incorrect date order, can't use current values.")
    flexi_tasks = None
auto_scheduler.remove_fixed_from_flexi(fixed_tasks, flexi_tasks)


@given(st.lists(task_strategy, min_size=1, max_size=50), st.fixed_dictionaries(weekly_mapping),
       st.dictionaries(safe_dates, pos_floats, max_size=50),
       st.dictionaries(safe_dates, st.dictionaries(sensible_strings, pos_float_times), max_size=50), st.booleans())
@example(tasks=flexi_tasks, regular_tasks=regular_fixed, single_fixed_work=one_off_fixed, fixed_tasks=fixed_tasks, weekends=True)
@settings(verbosity=Verbosity.verbose, deadline=None)
def test_no_missing_time_at_subjects(tasks: List[auto_scheduler.Task], regular_tasks: Dict[str, float],
                                     single_fixed_work: Dict[datetime.date, float],
                                     fixed_tasks: Dict[datetime.date, Dict[str, float]], weekends: bool):
    if tasks is None:
        return
    for task in tasks:
        assert task.due_date > task.start_date and task.due_date >= task.actual_due_date
        assert task.required_hours >= task.min_time >= auto_scheduler.time_inc
        assert task.required_hours / (task.due_date - task.start_date).days <= 24
        assume((weekends) or (task.due_date.weekday() not in [5, 6] and task.start_date.weekday() not in [5, 6]))
    tasks = sorted(sorted(tasks, key=lambda x: x.actual_due_date), key=lambda x: x.due_date)
    note('Calculating auto work')
    auto_work_per_day, work_on_days_to_due = auto_scheduler.calc_daily_work(tasks, regular_tasks, single_fixed_work,
                                                                            weekends)
    note(f'Auto work: {auto_work_per_day}')
    daily_subjects, missed_time = auto_scheduler.calc_daily_subjects(tasks, auto_work_per_day)
    note(f'Result: {daily_subjects}')
    daily_tasks = auto_scheduler.calc_daily_tasks(tasks, daily_subjects)
    note(f'Missed time: {missed_time}')
    assert missed_time == 0
    total_required_hours = sum([task.required_hours for task in tasks])
    total_auto_work = sum(auto_work_per_day.values())
    total_daily_subjects = sum([sum(daily_subjects[date].values()) for date in daily_subjects.keys()])
    total_daily_tasks = sum([sum(daily_tasks[date].values()) for date in daily_tasks.keys()])
    if not weekends:
        for date in daily_tasks.keys():
            assert date.weekday() not in [5, 6]
    note(
        f'Required hours: {total_required_hours}, Auto work: {total_auto_work}, '
        f'daily subjects: {total_daily_subjects}, daily tasks: {total_daily_tasks}')
    assert math.isclose(total_daily_subjects, total_auto_work) and math.isclose(total_auto_work, total_required_hours)


def prettify_task_list(input_list: list):
    output = '['
    for task in input_list:
        output += f'\n\tTask(title="{task.title}",\n\t\tsubtitle="{task.subtitle}"'
        for item in dir(task):
            if item[:1] != '__' and item[-2:] != '__' and item != 'title' and item != 'subtitle':
                output += f',\n\t\t{item}={getattr(task, item)}'
        output += ')'
    output += '\n]'
    return output


def test_current_shrink_fails():
    start_date = datetime.date.today()
    fixed_tasks, regular_fixed, one_off_fixed = auto_scheduler.load_fixed_tasks()
    try:
        flexi_tasks = auto_scheduler.load_flexi_tasks(start_date)
    except DateOrderError:
        print("Current has bad date ordering")
        return
    auto_scheduler.remove_fixed_from_flexi(fixed_tasks, flexi_tasks)

    flexi_tasks = [
        Task(title='Housework', subtitle='Housework', required_hours=0.03333333333333333, min_time=0.03333333333333333,
             start_date=datetime.date(2021, 5, 21), due_date=datetime.date(2021, 10, 10),
             actual_due_date=datetime.date(2021, 10, 10)),
        Task(title='Housework', subtitle='Make a meal', required_hours=0.06666666666666667,
             min_time=0.06666666666666667, start_date=datetime.date(2021, 5, 21), due_date=datetime.date(2021, 10, 24),
             actual_due_date=datetime.date(2021, 10, 24)),
        Task(title='Flight Vehicle Design', subtitle='Flight Vehicle Design', required_hours=22.016666666666666,
             min_time=0.25, start_date=datetime.date(2021, 5, 21), due_date=datetime.date(2021, 11, 1),
             actual_due_date=datetime.date(2021, 11, 1))]
    regular_fixed = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0.2833333333333333, 'Thursday': 0.2833333333333333,
                     'Friday': 0.3,
                     'Saturday': 0.3, 'Sunday': 0.3}
    one_off_fixed = {datetime.date(2021, 5, 25): 3.0}
    fixed_tasks = {}

    for task in flexi_tasks:
        if not (task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date):
            note(f'Required hours: {task.required_hours}')
            note(f'Min time: {task.min_time}')
            note(f'Time inc: {auto_scheduler.time_inc}')
            note(f'Due date: {task.due_date}')
            note(f'Start date: {task.start_date}')
            assert task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date
    flexi_tasks = sorted(sorted(flexi_tasks, key=lambda task: task.actual_due_date), key=lambda task: task.due_date)

    def calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks):
        sys.stdout = StringIO()
        flexi_per_day, _ = auto_scheduler.calc_daily_work(flexi_tasks, regular_fixed, one_off_fixed, True)
        _, missed_time = auto_scheduler.calc_daily_subjects(flexi_tasks, flexi_per_day)
        sys.stdout = sys.__stdout__
        return missed_time

    missed_time = calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks)

    if missed_time != 0:
        print('Failure')
        # Minimise flexi task list
        minimised = False
        while not minimised:
            print('Minimising task list')
            minimised = True
            tasks_to_remove: List[int] = []
            for index, task in enumerate(flexi_tasks):
                print(f'Minimising {task.subtitle}, index {index}')
                prev_required_hours = task.required_hours
                prev_min_time = task.min_time
                bounds: List[float] = [0, task.required_hours]
                bound_vals = [None, None]
                task.required_hours = bounds[0]
                task.min_time = min(prev_min_time, task.required_hours)
                bound_vals[0] = calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks)
                if bound_vals[0] != 0:
                    task.required_hours = bounds[0]
                    task.min_time = min(prev_min_time, task.required_hours)
                    tasks_to_remove.append(index)
                    print(f'Will remove {task.subtitle}, index {index}')
                else:
                    mid_pos = auto_scheduler.round_hours_to_minute((bounds[0] + bounds[1]) / 2)
                    while abs(bounds[1] - bounds[0]) > 2 * auto_scheduler.time_inc:
                        print(f'Bounds: {bounds}')
                        print(f'Bound vals: {bound_vals}')
                        mid_pos = auto_scheduler.round_hours_to_minute((bounds[0] + bounds[1]) / 2)
                        task.required_hours = mid_pos
                        task.min_time = min(prev_min_time, task.required_hours)
                        mid_val = calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks)
                        print(f'Mid val: {mid_val}')
                        if mid_val == 0:
                            bounds[0] = mid_pos
                        else:
                            bounds[1] = mid_pos
                    task.required_hours = bounds[1]
                    task.min_time = min(prev_min_time, task.required_hours)

                missed_time = calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks)
                if prev_required_hours != task.required_hours:
                    print(f'Reducing {task.subtitle} from {prev_required_hours} to {task.required_hours} resulted in'
                          f' {missed_time} hours of missed time.')
                    minimised = False
                assert task.required_hours >= task.min_time >= auto_scheduler.time_inc or task.required_hours == 0
            for task_index in reversed(tasks_to_remove):
                print(f'{flexi_tasks[task_index].subtitle} at index {task_index} no longer needed.')
                del flexi_tasks[task_index]
            print(f'Minimised to: {prettify_task_list(flexi_tasks)}')
            print(f'Missed time: {calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks)}')

        # Minimise regular fixed task list
        minimised = False
        while not minimised:
            minimised = True
            print('Minimising regular tasks')
            for day in regular_fixed.keys():
                prev_amount = regular_fixed[day]
                bounds = [0, regular_fixed[day]]
                regular_fixed[day] = bounds[0]
                if calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks) == 0:
                    while abs(bounds[1] - bounds[0]) > auto_scheduler.time_inc:
                        mid_pos = auto_scheduler.round_hours_to_minute((bounds[0] + bounds[1]) / 2)
                        regular_fixed[day] = mid_pos
                        if calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks) == 0:
                            bounds[0] = mid_pos
                        else:
                            bounds[1] = mid_pos
                    regular_fixed[day] = bounds[1]
                if regular_fixed[day] != prev_amount:
                    print(f'{day} improved from {prev_amount} to {regular_fixed[day]}')
                    minimised = False
            print(f'Minimised to: {regular_fixed}')
            print(f'Missed time: {calc_missed_time(flexi_tasks, regular_fixed, one_off_fixed, fixed_tasks)}')

        print(f'Final task list: {prettify_task_list(flexi_tasks)}')
        print(f'Final regular fixed: {regular_fixed}')
        print(flexi_tasks)
        assert missed_time == 0
    else:
        print('Passed')

    assert missed_time == 0


@given(st.just(2))
@settings(max_examples=1)
def test_current_no_missed(val):
    start_date = datetime.date.today()
    fixed_tasks, regular_fixed, one_off_fixed = auto_scheduler.load_fixed_tasks()
    try:
        flexi_tasks = auto_scheduler.load_flexi_tasks(start_date)
    except DateOrderError:
        print("Current has bad date ordering")
        return
    auto_scheduler.remove_fixed_from_flexi(fixed_tasks, flexi_tasks)

    for task in flexi_tasks:
        if not (task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date):
            note(f'Required hours: {task.required_hours}')
            note(f'Min time: {task.min_time}')
            note(f'Time inc: {auto_scheduler.time_inc}')
            note(f'Due date: {task.due_date}')
            note(f'Start date: {task.start_date}')
            assert task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date
    flexi_tasks = sorted(sorted(flexi_tasks, key=lambda task: task.actual_due_date), key=lambda task: task.due_date)

    flexi_per_day, work_on_days_to_due = auto_scheduler.calc_daily_work(flexi_tasks, regular_fixed, one_off_fixed, True)
    daily_subjects, missed_time = auto_scheduler.calc_daily_subjects(flexi_tasks, flexi_per_day)

    assert missed_time == 0


if __name__ == "__main__":
    test_invert_datetime_to_date()
    test_invert_decimal_to_timestring()
    test_getting_work()
    test_no_missing_time_at_subjects()
    test_current_no_missed()
    test_current_shrink_fails()
    print('tested')
