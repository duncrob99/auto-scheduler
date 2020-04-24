#!/usr/bin/env python
import io
import subprocess
import os
import datetime
from operator import itemgetter

day_fixed_work = io.open('day_fixed_work.txt')
one_off_tasks = io.open('one-off_tasks')
fixed_work_lines = day_fixed_work.readlines()
one_off_tasks_lines = one_off_tasks.readlines()

regular_working = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0}
weekday_conversion = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
one_off_working = {}

time_inc = 1/60

valid_input = False
while not valid_input:
    include_today = input("Include Today? [Y/n]: ")
    if include_today == "y" or include_today == "":
        include_today = True
        valid_input = True
    elif include_today == "n":
        include_today = False
        valid_input = True

valid_input = False
while not valid_input:
    include_weekends = input("Include weekends? [Y/n]: ") 
    if include_weekends == 'y' or include_weekends == "":
        include_weekends = True
        valid_input = True
    elif include_weekends == "n":
        include_weekends = False
        valid_input = True

valid_input = False
while not valid_input:
    reverse_output = input("Reverse output? [Y/n]: ")
    if reverse_output == "y" or reverse_output == "":
        reverse_output = True
        valid_input = True
    elif reverse_output == "n":
        reverse_output = False
        valid_input = True

screen_width = int(os.popen('stty size', 'r').read().split()[1])

if input("Clear terminal history? [Y/n]: ") in ['y', '']:
    subprocess.call('reset')
elif input("Separate output? [Y/n]: ") in ['y', '']:
    output = ''
    for j in range(screen_width):
        output += ':'
    for i in range(20):
        print(output)

def datetime_to_date_string(input_date):
    return str(input_date.day) + '/' + str(input_date.month) + '/' + str(input_date.year)[2:]


def date_string_to_datetime(input_date_string):
    split_string = input_date_string.split('/')
    try:
        day = int(split_string[0])
        month = int(split_string[1])
        year = int('20' + split_string[2])
    except IndexError:
        print("Invalid datestring:", input_date_string)
    try:
        return datetime.date(year, month, day)
    except ValueError:
        print("Invalid date:",year, month, day)


def decimal_to_timestring(value):
    hours = round(value - value % 1)
    minutes = round((value - hours) * 60)
    if minutes == 60:
        hours += 1
        minutes = 0

    if minutes >= 10:
        return str(hours) + ":" + str(minutes)
    else:
        return str(hours) + ":0" + str(minutes)


def timestring_to_decimal(timestring):
    split_time = timestring.split(':')
    hours = float(split_time[0])
    if len(split_time) > 1:
        minutes = float(split_time[1])
    else:
        minutes = 0
        decimal_time = hours + minutes / 60
        return decimal_time


def get_work_on_day(requested_day):
    weekday = weekday_conversion[requested_day.weekday()]
    regular_work = regular_working[weekday]
    if requested_day in one_off_working:
        one_off_work = one_off_working[requested_day]
        total_work = regular_work + one_off_work
    else:
        total_work = regular_work

    return total_work


# Bring fixed work data into memory structures
daily_tasks = {}
for day_info in fixed_work_lines:
    if day_info == '\n' or day_info[0] == '#': continue

    split_info = day_info.split(';')
    day = split_info[0]
    work_time = timestring_to_decimal(split_info[1].split('\n')[0])
    if day in regular_working.keys():
        regular_working[day] += work_time
    elif day in one_off_working.keys():
        one_off_working[date_string_to_datetime(day)] += work_time
    else:
        one_off_working[date_string_to_datetime(day)] = work_time

    # Deal with titled work data
    if len(split_info) >= 3:
        work_title = split_info[2].split('\n')[0]
        if day in regular_working.keys():
            #TODO: Deal with regulars
            pass
        else:
            date = date_string_to_datetime(day)
            if date in daily_tasks:
                if work_title in daily_tasks[date]:
                    daily_tasks[date][work_title] += work_time
                else:
                    daily_tasks[date][work_title] = work_time
            else:
                daily_tasks[date] = {}
                daily_tasks[date][work_title] = work_time

# Bring task list data into memory structures
tasks = []
due_dateless_task_indices = []
for index, task in enumerate(one_off_tasks_lines):
    split_info = task.split(';')
    
    if task[0] == '#' or split_info == '\n' or '\n' in split_info: continue

    title = split_info[0]
    try:
        required_hours = timestring_to_decimal(split_info[1].split(' ')[1])
    except IndexError:
        print(split_info)

    due_date = split_info[2].split(' ')[1].split('\n')[0]
    if len(split_info) >= 4:
        min_time = timestring_to_decimal(split_info[3].split(' ')[1])
    else:
        min_time = 1

    if due_date == 'none':
        due_dateless_task_indices.append(index)
        due_date = date_string_to_datetime('1/1/01')
    elif len(due_date.split('-')) > 1:
        due_date = due_date.split('-')
        start_date = max(date_string_to_datetime(due_date[0]), datetime.datetime.now().date())
        due_date = date_string_to_datetime(due_date[1])
    else:
        start_date = datetime.datetime.now().date()
        due_date = date_string_to_datetime(due_date)

    due_date = max(due_date, datetime.datetime.now().date() + datetime.timedelta(days=1 if include_today else 2))

    if len(split_info) >= 5:
        subtitle = split_info[4]
    else:
        subtitle = title

    if subtitle[0] == ' ':
        subtitle = subtitle[1:]

    if subtitle[-1] == '\n':
        subtitle = subtitle[:-1]

    tasks.append([title, required_hours, start_date, due_date, min_time, subtitle])

# Remove set work from task requirements
for date in daily_tasks:
    for title in daily_tasks[date]:
        for task in tasks:
            if title == task[0]:
                task[1] -= daily_tasks[date][title]

# Set due date for any tasks without due date to maximum due date
max_due_date = sorted(tasks, key=itemgetter(3))[-1][3]
for index in due_dateless_task_indices:
    tasks[index][3] = max_due_date

# Sort tasks by due date
tasks = sorted(tasks, key=itemgetter(3))

# Work out how many hours to work a day
required_hour_sum = 0
auto_work_per_day = {}
work_on_days_to_due = {}
for task in tasks:
    title, required_hours, start_date, due_date, min_time, subtitle = task

    # Get list of days which could possibly be used
    if include_today or start_date != datetime.datetime.now().date():
        available_days = [start_date + datetime.timedelta(days=x) for x in range(0, (due_date - start_date).days)]
    else:
        available_days = [start_date + datetime.timedelta(days=x) for x in range(1, (due_date - start_date).days)]

    # Get total work on each day and slate weekends for removal if necessary
    indices_to_delete = []
    for index, date in enumerate(available_days):
        if date.weekday() in [6, 5] and not include_weekends:
            indices_to_delete.append(index)
            continue
        if date in auto_work_per_day:
            work_on_days_to_due[date] = get_work_on_day(date) + auto_work_per_day[date]
        else:
            work_on_days_to_due[date] = get_work_on_day(date)

    # Can't delete while iterating over list, so actually remove weekends now
    for index in reversed(indices_to_delete):
        del available_days[index]

    # Add hours to day with smallest amount of work so far
    while required_hours > 0 and len(work_on_days_to_due) > 0:
        min_work_day = min(available_days, key=lambda x: work_on_days_to_due[x])
        auto_work_to_add = min([min_time, required_hours])
        if min_work_day in auto_work_per_day:
            auto_work_per_day[min_work_day] += auto_work_to_add
            work_on_days_to_due[min_work_day] += auto_work_to_add
        elif min_work_day in work_on_days_to_due:
            auto_work_per_day[min_work_day] = auto_work_to_add
            work_on_days_to_due[min_work_day] += auto_work_to_add
        else:
            auto_work_per_day[min_work_day] = auto_work_to_add
            work_on_days_to_due[min_work_day] += auto_work_to_add

        required_hours -= auto_work_to_add

# Assign subjects to each day
daily_titles = {}
for task in tasks:
    title, required_hours, start_date, due_date, min_time, subtitle = task

    available_days = [start_date + datetime.timedelta(days=x) for x in range(0, (due_date - start_date).days)]

    while required_hours > 0 and len(available_days) > 0:
        previous_hours = required_hours
        for date in available_days:
            if date in auto_work_per_day:
                if required_hours > 0 and auto_work_per_day[date] > 0:
                    if auto_work_per_day[date] < min_time:
                        continue
                    if not date in daily_tasks or not title in daily_tasks[date]:
                        auto_work_to_add = min_time
                    elif daily_tasks[date][title] < min_time:
                        auto_work_to_add = min_time - daily_tasks[date][title]
                    else:
                        auto_work_to_add = min([min_time, required_hours, auto_work_per_day[date]])

                    # Safely add work to daily tasks
                    if date in daily_tasks:
                        if title in daily_tasks[date]:
                            daily_tasks[date][title] += auto_work_to_add
                        else:
                            daily_tasks[date][title] = auto_work_to_add

                    else:
                        daily_tasks[date] = {title: auto_work_to_add}

                    # Update total amount of auto-work
                    auto_work_per_day[date] -= auto_work_to_add

                    # Safely add work to daily titles
                    if date in daily_titles:
                        if title in daily_titles[date]:
                            daily_titles[date][title] += auto_work_to_add
                        else:
                            daily_titles[date][title] = auto_work_to_add
                    else:
                        daily_titles[date] = {title: auto_work_to_add}

                    required_hours -= auto_work_to_add

        if previous_hours == required_hours:
            print("Not enough time for " + title + " (" + subtitle + ") with " + str(required_hours) + " hours extra.")
            break
    if len(available_days) <= 0:
        if required_hours > 1:
            print('Do ' + str(required_hours) + ' hours of ' + subtitle + ' now!')
        else:
            print('Do ' + str(required_hours) + ' hour of ' + subtitle + ' now!')

# Assign specific tasks to dates
daily_subtitles = {}
for task in tasks:
    title, required_hours, start_date, due_date, min_time, subtitle = task
    if due_date == datetime.datetime.now().date() + datetime.timedelta(days=1):
        subtitle = "(DUE) " + subtitle

    for date in sorted(filter(lambda x: x >= start_date, daily_titles)):
        if title in daily_titles[date] and required_hours > 0 and daily_titles[date][title] > 0:
            auto_work_to_add = min(required_hours, daily_titles[date][title])
            required_hours -= auto_work_to_add
            daily_titles[date][title] -= auto_work_to_add
            if required_hours <= 0:
                subtitle = "(Complete) " + subtitle
            if date in daily_subtitles:
                if subtitle in daily_subtitles[date]:
                    daily_subtitles[date][subtitle] += auto_work_to_add
                else:
                    daily_subtitles[date][subtitle] = auto_work_to_add
            else:
                daily_subtitles[date] = {subtitle: auto_work_to_add}
    if required_hours > 0:
        print('%s: %s' % (subtitle, required_hours))

# Display results
actual_hours_sum = 0
for date in sorted(daily_subtitles, reverse=reverse_output):
    total_auto = 0
    for task in daily_subtitles[date]:
        total_auto += daily_subtitles[date][task]

    # Create correct number of title dashes
    output = weekday_conversion[date.weekday()] + ' ' + str(date) + ' (' + decimal_to_timestring(total_auto) + ' auto/' + decimal_to_timestring(work_on_days_to_due[date]) + ' total)'
    cur_side_left = True
    while len(output) < screen_width:
        if cur_side_left:
            output = '-' + output
        else:
            output = output + '-'

        cur_side_left = not cur_side_left

    print(output)

    for task in daily_subtitles[date]:
        print(task + ': ' + decimal_to_timestring(daily_subtitles[date][task]))
        actual_hours_sum += daily_subtitles[date][task]
