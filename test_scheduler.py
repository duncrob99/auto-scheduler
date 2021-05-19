import datetime
from typing import List, Dict

from hypothesis import Phase, settings, Verbosity, given, note, strategies as st, assume

import auto_scheduler

safe_floats = st.floats(allow_nan=False, allow_infinity=False)
safe_dates = st.dates(min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2010, 12, 31))
early_dates = st.dates(min_value=datetime.date(2000, 1, 1), max_value=datetime.date(2000, 12, 31))
pos_floats = st.floats(allow_nan=False, allow_infinity=False, min_value=0)
sensible_floats = st.floats(allow_nan=False, allow_infinity=False, min_value=0, max_value=24)
sensible_times = st.builds(lambda mins: mins / 60, st.integers(min_value=0, max_value=24*60))
pos_float_times = st.builds(lambda mins: mins / 60, st.integers(min_value=1, max_value=24*60))
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
       st.dictionaries(st.dates(), st.floats()))
@settings(verbosity=Verbosity.verbose)
def test_getting_work(requested_day, weekly_work, single_fixed_work):
    weekday = weekdays[requested_day.weekday()]
    answer = (weekly_work[weekday] if weekday in weekly_work else 0) + (
        single_fixed_work[requested_day] if requested_day in single_fixed_work else 0)
    assert auto_scheduler.get_work_on_day(requested_day, weekly_work, single_fixed_work) == answer


@given(st.lists(task_strategy, min_size=1, max_size=5), st.fixed_dictionaries(weekly_mapping),
       st.dictionaries(safe_dates, pos_floats, max_size=5),
       st.dictionaries(safe_dates, st.dictionaries(sensible_strings, pos_floats), max_size=5))
def test_no_missing_time_at_subjects(tasks: List[auto_scheduler.Task], regular_tasks: Dict[str, float],
                                     single_fixed_work: Dict[datetime.date, float],
                                     fixed_tasks: Dict[datetime.date, Dict[str, float]]):
    [assume(task.min_time < task.required_hours and task.due_date > task.start_date and task.min_time != 0) for task in tasks]
    auto_work_per_day, work_on_days_to_due = auto_scheduler.calc_daily_work(tasks, regular_tasks, single_fixed_work,
                                                                            True)
    daily_subjects, missed_time = auto_scheduler.calc_daily_subjects(tasks, fixed_tasks, auto_work_per_day)
    note(f'Auto work: {auto_work_per_day}')
    note(f'Result: {daily_subjects}')
    if missed_time == 0:
        note('PASSED!')
    assert missed_time == 0


if __name__ == "__main__":
    test_no_missing_time_at_subjects()
    print('tested')
