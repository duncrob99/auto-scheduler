import io
import datetime
from operator import itemgetter

day_fixed_work = io.open('day_fixed_work.txt')
one_off_tasks = io.open('one-off_tasks')
fixed_work_lines = day_fixed_work.readlines()
one_off_tasks_lines = one_off_tasks.readlines()

regular_working = {'Monday': 0, 'Tuesday': 0, 'Wednesday': 0, 'Thursday': 0, 'Friday': 0, 'Saturday': 0, 'Sunday': 0}
weekday_conversion = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
one_off_working = {}

valid_input = False
while not valid_input:
    include_today = input("Include Today? (y/n): ")
    if include_today == "y" or include_today == "":
        include_today = True
        valid_input = True
    elif include_today == "n":
        include_today = False
        valid_input = True

valid_input = False
while not valid_input:
    include_weekends = input("Include weekends? (y/n): ") 
    if include_weekends == 'y' or include_weekends == "":
        include_weekends = True
        valid_input = True
    elif include_weekends == "n":
        include_weekends = False
        valid_input = True

valid_input = False
while not valid_input:
    reverse_output = input("Reverse output? (y/n): ")
    if reverse_output == "y" or reverse_output == "":
        reverse_output = True
        valid_input = True
    elif reverse_output == "n":
        reverse_output = False
        valid_input = True

if input("Separate output? (y/n): ") in ['y', '']:
    for i in range(0, 5):
        print(' ')

screen_width = 64


def datetime_to_date_string(input_date):
    return str(input_date.day) + '/' + str(input_date.month) + '/' + str(input_date.year)[2:]


def date_string_to_datetime(input_date_string):
    split_string = input_date_string.split('/')
    day = int(split_string[0])
    month = int(split_string[1])
    year = int('20' + split_string[2])
    return datetime.date(year, month, day)


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
for day_info in fixed_work_lines:
    if day_info != '\n':
        split_info = day_info.split(' ')
        day = split_info[0]
        work_time = float(split_info[1].split('\n')[0])
        if day in regular_working.keys():
            regular_working[day] += work_time
        elif day in one_off_working.keys():
            one_off_working[date_string_to_datetime(day)] += work_time
        else:
            one_off_working[date_string_to_datetime(day)] = work_time


# Bring task list data into memory structures
tasks = []
for task in one_off_tasks_lines:
    split_info = task.split(';')
    if split_info == '\n' or '\n' in split_info:
        break
    title = split_info[0]
    try:
        required_hours = split_info[1].split(' ')[1]
    except IndexError:
        print(split_info)
    due_date = split_info[2].split(' ')[1].split('\n')[0]
    if len(due_date.split('-')) > 1:
        due_date = due_date.split('-')
        start_date = date_string_to_datetime(due_date[0])
        due_date = date_string_to_datetime(due_date[1])
    else:
        start_date = datetime.datetime.now().date()
        due_date = date_string_to_datetime(due_date)
    tasks.append([title, required_hours, start_date, due_date])
# Sort tasks by due date
tasks = sorted(tasks, key=itemgetter(3))

# Work out how many hours to work a day
auto_work_per_day = {}
work_on_days_to_due = {}
for task in tasks:
    title = task[0]
    required_hours = float(task[1])
    start_date = max(task[2], datetime.datetime.now().date())
    if include_today:
        due_date = max(task[3], datetime.datetime.now().date() + datetime.timedelta(days=1))
    else:
        due_date = max(task[3], datetime.datetime.now().date() + datetime.timedelta(days=2))


    # Get list of days which could possibly be used
    if include_today or start_date != datetime.datetime.now().date():
        available_days = [start_date + datetime.timedelta(days=x) for x in range(0, (due_date - start_date).days)]
    else:
        available_days = [start_date + datetime.timedelta(days=x) for x in range(1, (due_date - start_date).days)]

    # Get total work on each day and remove weekends
    for index, date in enumerate(available_days):
        if date.weekday() in [6, 5] and not include_weekends:
            del available_days[index] 
            continue
        if date in auto_work_per_day:
            work_on_days_to_due[date] = get_work_on_day(date) + auto_work_per_day[date]
        else:
            work_on_days_to_due[date] = get_work_on_day(date)

    # Add hours to day with smallest amount of work so far
    while required_hours > 0 and len(work_on_days_to_due) > 0:
        min_work_day = min(work_on_days_to_due, key=lambda x: work_on_days_to_due[x])
        auto_work_to_add = min([1, required_hours])
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


# Assign specific tasks to each day
daily_tasks = {}
for task in tasks:
    title = task[0]
    required_hours = float(task[1])
    start_date = task[2]
    if include_today:
        due_date = max(task[3], datetime.datetime.now().date() + datetime.timedelta(days=1))
    else:
        due_date = max(task[3], datetime.datetime.now().date() + datetime.timedelta(days=2))
    available_days = [start_date + datetime.timedelta(days=x) for x in range(0, (due_date - start_date).days)]
    while required_hours > 0 and len(available_days) > 0:
        previous_hours = required_hours
        for date in available_days:
            if date in auto_work_per_day:
                if required_hours > 0 and auto_work_per_day[date] > 0:
                    auto_work_to_add = min([1, required_hours, auto_work_per_day[date]])
                    if date in daily_tasks:
                        if title in daily_tasks[date]:
                            daily_tasks[date][title] += auto_work_to_add
                            auto_work_per_day[date] -= auto_work_to_add
                        else:
                            daily_tasks[date][title] = auto_work_to_add
                            auto_work_per_day[date] -= auto_work_to_add
                    else:
                        daily_tasks[date] = {title: auto_work_to_add}
                        auto_work_per_day[date] -= auto_work_to_add
                    required_hours -= 1
        if previous_hours == required_hours:
            print("Not enough time for " + title + " with " + str(required_hours) + " hours extra.")
            break
    if len(available_days) <= 0:
        if required_hours > 1:
            print('Do ' + str(required_hours) + ' hours of ' + title + ' now!')
        else:
            print('Do ' + str(required_hours) + ' hour of ' + title + ' now!')


# Display results
for date in sorted(daily_tasks, reverse=reverse_output):
    total_auto = 0
    for task in daily_tasks[date]:
        total_auto += daily_tasks[date][task]
    # Create correct number of title dashes
    output = weekday_conversion[date.weekday()] + ' ' + str(date) + ' (' + str(total_auto) + ' auto/' + str(work_on_days_to_due[date]) + ' total hours)'
    cur_side_left = True
    while len(output) < screen_width:
        if cur_side_left:
            output = '-' + output
        else:
            output = output + '-'
        cur_side_left = not cur_side_left
    print(output)
    for task in daily_tasks[date]:
        print(task + ': ' + str(daily_tasks[date][task]))
