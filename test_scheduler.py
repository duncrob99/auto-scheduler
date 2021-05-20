import datetime
import time
from typing import List, Dict

from hypothesis import example, HealthCheck, settings, Verbosity, given, note, strategies as st, assume

import auto_scheduler
from auto_scheduler import Task

safe_floats = st.floats(allow_nan=False, allow_infinity=False)
safe_dates = st.dates(min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2010, 12, 31))
early_dates = st.dates(min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2000, 12, 31))
pos_floats = st.floats(allow_nan=False, allow_infinity=False, min_value=0)
sensible_floats = st.floats(allow_nan=False, allow_infinity=False, min_value=0, max_value=24)
sensible_times = st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=24 * 60))
pos_float_times = st.builds(lambda mins: mins / 60, st.integers(min_value=1, max_value=24 * 60))
sensible_strings = st.text(st.characters(whitelist_categories=['L', 'N', 'P', 'Sc', 'Zs']), max_size=10)
task_strategy = st.builds(auto_scheduler.Task, sensible_strings, sensible_strings, sensible_times, sensible_times,
                          early_dates, early_dates, early_dates)


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
flexi_tasks = auto_scheduler.load_flexi_tasks(start_date)
auto_scheduler.remove_fixed_from_flexi(fixed_tasks, flexi_tasks)


@given(st.lists(task_strategy, min_size=1), st.fixed_dictionaries(weekly_mapping),
       st.dictionaries(safe_dates, pos_floats),
       st.dictionaries(safe_dates, st.dictionaries(sensible_strings, pos_floats)))
@example(tasks=flexi_tasks, regular_tasks=regular_fixed, single_fixed_work=one_off_fixed, fixed_tasks=fixed_tasks)
@example(tasks=[auto_scheduler.Task(title='', subtitle='', required_hours=0.05, min_time=0.03333333333333333,
                                    start_date=datetime.date(2000, 1, 1), due_date=datetime.date(2000, 1, 4),
                                    actual_due_date=datetime.date(2000, 1, 1)),
                auto_scheduler.Task(title='', subtitle='', required_hours=0.05, min_time=0.03333333333333333,
                                    start_date=datetime.date(2000, 1, 1), due_date=datetime.date(2000, 1, 2),
                                    actual_due_date=datetime.date(2000, 1, 1))],
         regular_tasks={'Friday': 0.0,
                        'Monday': 0.0,
                        'Saturday': 0.016666666666666666,
                        'Sunday': 0.0,
                        'Thursday': 0.0,
                        'Tuesday': 0.0,
                        'Wednesday': 0.0},
         single_fixed_work={},
         fixed_tasks={})
@settings(max_examples=1, suppress_health_check=[HealthCheck.filter_too_much, HealthCheck.too_slow], verbosity=Verbosity.verbose)
def test_no_missing_time_at_subjects(tasks: List[auto_scheduler.Task], regular_tasks: Dict[str, float],
                                     single_fixed_work: Dict[datetime.date, float],
                                     fixed_tasks: Dict[datetime.date, Dict[str, float]]):
    [assume(task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date) for task
     in tasks]
    tasks = sorted(sorted(tasks, key=lambda x: x.actual_due_date), key=lambda x: x.due_date)
    auto_work_per_day, work_on_days_to_due = auto_scheduler.calc_daily_work(tasks, regular_tasks, single_fixed_work,
                                                                            True)
    note(f'Auto work: {auto_work_per_day}')
    daily_subjects, missed_time = auto_scheduler.calc_daily_subjects(tasks, fixed_tasks, auto_work_per_day)
    note(f'Result: {daily_subjects}')
    note(f'Missed time: {missed_time}')
    assert missed_time == 0


@given(st.just(2))
@settings(max_examples=1)
def test_current_no_missed(val):
    start_date = datetime.date.today()
    fixed_tasks, regular_fixed, one_off_fixed = auto_scheduler.load_fixed_tasks()
    flexi_tasks = auto_scheduler.load_flexi_tasks(start_date)
    auto_scheduler.remove_fixed_from_flexi(fixed_tasks, flexi_tasks)

    for task in flexi_tasks:
        if not(task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date):
            note(f'Required hours: {task.required_hours}')
            note(f'Min time: {task.min_time}')
            note(f'Time inc: {auto_scheduler.time_inc}')
            note(f'Due date: {task.due_date}')
            note(f'Start date: {task.start_date}')
            assert task.required_hours >= task.min_time >= auto_scheduler.time_inc and task.due_date > task.start_date
    flexi_tasks = sorted(sorted(flexi_tasks, key=lambda task: task.actual_due_date), key=lambda task: task.due_date)

    flexi_per_day, work_on_days_to_due = auto_scheduler.calc_daily_work(flexi_tasks, regular_fixed, one_off_fixed, True)
    daily_titles, missed_time = auto_scheduler.calc_daily_subjects(flexi_tasks, fixed_tasks, flexi_per_day)

    assert missed_time == 0


if __name__ == "__main__":
    test_invert_datetime_to_date()
    test_invert_decimal_to_timestring()
    test_getting_work()
    test_no_missing_time_at_subjects()
    #test_current_no_missed()
    print('tested')
