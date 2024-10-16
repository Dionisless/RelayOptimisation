'''
Файл с функциями анализа защит 
'''

import kar_mrtkz as ktkz
import mrtkz3 as mrtkz
import pandas as pd
import time

'''
Генерация подрежимов,
Здесь 3 варианта
1) добавление подрежимов перебором в каком-то поясе отключений скольки-то линий вокруг одной линии generate_submodels_one_line
2) добавление подрежимов перебором в каком-то поясе скольки-то линий для каждой линии generate_submodels
--- В будущем ---
3) Просто добавить строку подрежимаto
4) 

'''
# Создание подрежимов по всей сети
def generate_submodels_one_line(mdl, line, max_belt_range=2, num_of_enum_lines=1, step=0.05, kz_types=['A0']):
    id = 0  # Инициализация счетчика ID
    submdl_dict = {}
    # Генерация списка поясных зон для данной линии
    p_off_list = ktkz.line_enumiration(mdl, line, max_belt_range=max_belt_range, num_of_enum_lines=num_of_enum_lines, 
                                       list_of_belts_for_enum='', return_names=True, 
                                       show_info=False, return_as_list=True)
    
    # Перебор поясных зон
    for p_off in p_off_list:
        # Перебор процентного значения (0% до 100%) с заданным шагом
        for percent in range(0, 100, int(step * 100)):   # Используем np.arange для работы с дробными числами
            perc = percent/100
            # Перебор типов короткого замыкания
            for kz_type in kz_types:
                id += 1  # Увеличение счетчика ID
                
                # Создание строки данных для текущеq подмоделb
                submdl_row = {'id': id, 'line_kz': line.name, 'kz_type': kz_type, 'percent': perc, 'p_off': p_off}
                
                
                # Добавление текущего режима в общий словарь
                submdl_dict[id] = submdl_row  # Добавляем строку с данными в словарь
    return submdl_dict
# пример
#line = ktkz.p_search(mdl, p_name = 'PS1-PS2')
#submdl_one_line_dict = generate_submodels_one_line(mdl, line, max_belt_range=2, #num_of_enum_lines=1, step=0.05, kz_types=['A0'])



# Создание подрежимов по всей сети
def generate_submodels(mdl, max_belt_range=2, num_of_enum_lines=1, step=0.05, kz_types=['A0']):
    id = 0  # Инициализация счетчика ID
    submdl_dict = {}
    # Перебор всех линий в модели
    for line in mdl.bp:
        # Генерация списка поясных зон для данной линии
        p_off_list = ktkz.line_enumiration(mdl, line, max_belt_range=max_belt_range, num_of_enum_lines=num_of_enum_lines, 
                                           list_of_belts_for_enum='', return_names=True, 
                                           show_info=False, return_as_list=True)
        
        # Перебор поясных зон
        for p_off in p_off_list:
            # Перебор процентного значения (0% до 100%) с заданным шагом
            for percent in range(0, 100, int(step * 100)):   # Используем np.arange для работы с дробными числами
                perc = percent/100
                # Перебор типов короткого замыкания
                for kz_type in kz_types:
                    id += 1  # Увеличение счетчика ID
                    
                    # Создание строки данных для текущеq подмоделb
                    submdl_row = {'id': id, 'line_kz': line.name, 'kz_type': kz_type, 'percent': perc, 'p_off': p_off}
                    
                    
                    # Добавление текущего режима в общий словарь
                    submdl_dict[id] = submdl_row  # Добавляем строку с данными в словарь
    return submdl_dict
# пример
#submdl_dict = generate_submodels(mdl, max_belt_range=2, num_of_enum_lines=1, step=0.33, kz_types=['A0'])
#len(submdl_dict)

'''
$$$$$$$ Бэкап функции, удалить, если все будет норм
Функция для анализа отключений релейной защиты. Возвращает словарь с данными отключения
'''
# Функция для анализа отключений релейной защиты. Возвращает словарь с данными отключения
'''
def analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False):
    """
    Функция для анализа отключений релейной защиты.

    Аргументы:
    mdl -- основная модель системы
    submdl_dict -- словарь подмоделей с информацией о линиях, процентах отключений и типах КЗ
    log -- флаг для вывода логов (по умолчанию False)
    range_prot_analyse - флаг для выбора рассчетов ближнего или дальнего резервирования False
    
    Возвращает:
    off_result -- словарь с результатами отключений
    """
    # Засекаем начальное время
    t1 = time.time()
    cut_id = 0
    off_result = {}  # Результаты отключений
    base_t_dict = {}  # Словарь для хранения времени срабатывания защит

    # Сохраняем базовое время защит для каждой защиты в модели
    for d in mdl.bd:
        base_t_dict[d.id] = d.t

    # Проходим по каждому элементу в подмоделях
    for submdl_id in submdl_dict:

        # Извлекаем данные для текущей подмодели
        line = submdl_dict[submdl_id]['line_kz']
        percent = submdl_dict[submdl_id]['percent']
        p_off = submdl_dict[submdl_id]['p_off']
        kz_type = submdl_dict[submdl_id]['kz_type']
        
        # Поиск линии по имени
        line_obj = ktkz.p_search(mdl, p_name=line)
        
        # Создаем подмодель с учётом процента линии и типа КЗ
        submdl = ktkz.kz_q(mdl, line=line_obj, percentage_of_line=percent, show_G=False, show_par=False, kaskade=False)
        
        # Удаление мощности для подмодели на определённой поясной зоне
        submdl = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False, node = submdl.bq[-1].name)
        
        # Расчёт КЗ для подмодели
        KZ1 = mrtkz.N(submdl, 'KZ', submdl.bq[-1], kz_type)
        
        # Выполняем расчёт для подмодели
        submdl.Calc()
        
        t=0
        p_off = ()
        t_dict = base_t_dict

        while True:
            # Пересчёт подмодели с новыми условиями
            submdl_temp = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False)
            submdl_temp.Calc()

            # Проверяем, отключилось ли КЗ
            
            try: 
                I0_kz = submdl_temp.bn[0].res('I0', 'M') # если узел кз исчез, значит удалили все ветви вокруг, КЗ отключено
                #print('Ток в точке КЗ',submdl_temp.bn[0].res('I0', 'M'))
            except: 
                off_result_row = {'id': -7, 't': t, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.id, 'line': 0, 'I0_line': I0_kz}   
                off_result[cut_id] = off_result_row  # Добавление отключения в общий результат
                cut_id+=1
                break
            if not I0_kz>10:
                off_result_row = {'id': -7, 't': t, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.id, 'line': 0, 'I0_line': I0_kz}   
                off_result[cut_id] = off_result_row  # Добавление отключения в общий результат
                cut_id+=1
                break

            # Поиск защит, которые чувствуют КЗ
            prot_dict = {}
            for p in submdl_temp.bp:
                I0 = p.res1(['I0'], 'M')['I0']
                ang = p.res1(['I0'], '<f')['I0']
                for d1 in p.q1_def:
                    if I0 >= d1.I0 and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                        did = d1.id
                        try: k_ch = d1.I0 / I0
                        except: k_ch = 0
                        prot_dict[did] = {'id': did, 'line': d1.p.name, 't': t_dict[did], 'k_ch': k_ch, 'line_id': d1.p.id}
                for d2 in p.q2_def:
                    if I0 >= d2.I0 and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                        did = d2.id
                        try: k_ch = d1.I0 / I0
                        except: k_ch = 0
                        prot_dict[did] = {'id': did, 'line': d2.p.name, 't': t_dict[did], 'k_ch': k_ch, 'line_id': d2.p.id}

            # Если ни одна защита не сработала
            if prot_dict == {}:
                off_result_row = {'id': -666, 't': t, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.id, 'line': 0, 'I0_line': I0_kz}   
                off_result[cut_id] = off_result_row  # Добавление результата в общий словарь
                cut_id += 1
                
                break

            # Обрабатываем сработавшие защиты
            prot_worked = False
            # находим защиту с мин временем срабатывания
            temp_t_list=[]
            t=0
            for p_id in prot_dict:
                 temp_t_list += [prot_dict[p_id]['t']]
            t = min(temp_t_list)
            #print(t)
            for p_id in prot_dict:
                if prot_dict[p_id]['line'] in p_off or (range_prot_analyse and prot_dict[p_id]['line'] == line):
                    continue


                else:
                    if t_dict[p_id] == t:
                        off_result_row = {'id': p_id, 't': prot_dict[p_id]['t'], 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': prot_dict[p_id]['k_ch'], 'line_kz':line_obj.id, 'line': prot_dict[p_id]['line_id'], 'I0_line': I0_kz}   
                        off_result[cut_id] = off_result_row  # Добавление в результат
                        cut_id += 1
                        p_off = p_off + (prot_dict[p_id]['line'],)
                        #print(off_result_row)
                    else:
                        t_dict[p_id] -= t

    # Засекаем конечное время и выводим время анализа, если включен лог
    t2 = time.time()
    if log:
        print(f"Время анализа: {t2 - t1} секунд")

    return off_result
'''

# Функция для анализа отключений релейной защиты. Возвращает словарь с данными отключения
def analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False, print_G=False):
    """
    Функция для анализа отключений релейной защиты.

    Аргументы:
    mdl -- основная модель системы
    submdl_dict -- словарь подмоделей с информацией о линиях, процентах отключений и типах КЗ
    log -- флаг для вывода логов (по умолчанию False)
    range_prot_analyse - флаг для выбора рассчетов ближнего или дальнего резервирования False
    
    Возвращает:
    off_result -- словарь с результатами отключений
    """
    # Засекаем начальное время
    t1 = time.time()
    cut_id = 0
    off_result = {}  # Результаты отключений
    base_t_dict = {}  # Словарь для хранения времени срабатывания защит

    # Сохраняем базовое время защит для каждой защиты в модели
    for d in mdl.bd:
        base_t_dict[d.stat_id] = d.t
    # Проходим по каждому элементу в подмоделях
    for submdl_id in submdl_dict:

        # Извлекаем данные для текущей подмодели
        line = submdl_dict[submdl_id]['line_kz']
        percent = submdl_dict[submdl_id]['percent']
        p_off = submdl_dict[submdl_id]['p_off']
        kz_type = submdl_dict[submdl_id]['kz_type']
        
        # Поиск линии по имени
        line_obj = ktkz.p_search(mdl, p_name=line)
        
        # Создаем подмодель с учётом процента линии и типа КЗ
        submdl = ktkz.kz_q(mdl, line=line_obj, percentage_of_line=percent, show_G=False, show_par=False, kaskade=False)
        
        # Удаление мощности для подмодели на определённой поясной зоне
        submdl = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False, node = False)#submdl.bq[-1].name)
        
        # Расчёт КЗ для подмодели
        KZ1 = mrtkz.N(submdl, 'KZ', submdl.bq[-1], kz_type)
        
        # Выполняем расчёт для подмодели
        submdl.Calc()
        
        t=0
        p_off = ()
        t_dict = base_t_dict
        t_total = 0
        if print_G: print('Начат анализ подрежима №', submdl_id, submdl_dict[submdl_id])
        while True:
            # Пересчёт подмодели с новыми условиями
            submdl_temp = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False)
            submdl_temp.Calc()
            if print_G:
                
                ktkz.print_G(submdl_temp, I=True)
            # Проверяем, отключилось ли КЗ
            try: 
                I0_kz = submdl_temp.bn[0].res('I0', 'M') # если узел кз исчез, значит удалили все ветви вокруг, КЗ отключено
                #print('Ток в точке КЗ',submdl_temp.bn[0].res('I0', 'M'))
            except: 
                off_result_row = {'id': -7, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.name, 'line': 0, 'I0_line': 0, 'prot_id':-1}   
                off_result[cut_id] = off_result_row  # Добавление отключения в общий результат
                cut_id+=1
                break
            if not I0_kz>10:
                off_result_row = {'id': -7, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.name, 'line': 0, 'I0_line': I0_kz, 'prot_id':-1}   
                off_result[cut_id] = off_result_row  # Добавление отключения в общий результат
                cut_id+=1
                break

            # Поиск защит, которые чувствуют КЗ
            prot_dict = {}
            for p in submdl_temp.bp:
                I0 = p.res1(['I0'], 'M')['I0']
                ang = p.res1(['I0'], '<f')['I0']
                for d1 in p.q1_def:
                    if I0 >= d1.I0 and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                        did = d1.stat_id
                        try: k_ch = d1.I0 / I0
                        except: k_ch = 0
                        
                        prot_dict[did] = {'id': did, 'line': d1.p.name, 't': t_dict[did], 'k_ch': k_ch, 'I0_line':[I0, ang]}
                for d2 in p.q2_def:
                    if I0 >= d2.I0 and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                        did = d2.stat_id
                        try: k_ch = d1.I0 / I0
                        except: k_ch = 0
                        prot_dict[did] = {'id': did, 'line': d2.p.name, 't': t_dict[did], 'k_ch': k_ch, 'I0_line':[I0, ang]}

            # Если ни одна защита не сработала
            if prot_dict == {}:
                off_result_row = {'id': -666, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.name, 'line': 0, 'I0_line': I0_kz, 'prot_id':-1}   
                off_result[cut_id] = off_result_row  # Добавление результата в общий словарь
                cut_id += 1
                
                break

            # Обрабатываем сработавшие защиты
            prot_worked = False
            # находим защиту с мин временем срабатывания
            temp_t_list=[]
            t=0
            for p_id in prot_dict:
                temp_t_list += [prot_dict[p_id]['t']]
            t = min(temp_t_list)
            t_total += t
            #print(t)
            for p_id in prot_dict:
                if prot_dict[p_id]['line'] in p_off or (range_prot_analyse and prot_dict[p_id]['line'] == line):
                    continue


                else:
                    if t_dict[p_id] == t:
                        off_result_row = {'id': p_id, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': prot_dict[p_id]['k_ch'], 'line_kz':line_obj.name, 'line': prot_dict[p_id]['line'], 'I0_line': prot_dict[p_id]['I0_line'], 'prot_id':p_id}   
                        off_result[cut_id] = off_result_row  # Добавление в результат
                        cut_id += 1
                        p_off = p_off + (prot_dict[p_id]['line'],)
                        
                        if print_G:
                            off = prot_dict[p_id]['line']
                            print(f'Отключена линия {off}')
                        #print(off_result_row)
                    else:
                        t_dict[p_id] -= t
    #prot_dict[p_id]['t']
    # Засекаем конечное время и выводим время анализа, если включен лог
    t2 = time.time()
    if log:
        print(f"Время анализа: {t2 - t1} секунд")

    return off_result
    
# Функция выводит датафрейм с анализом срабатывания защит, не нужна для обучения, но удобная
def prot_work_df(mdl, prot_work, submdl_dict):
    # Инициализация пустого списка для строк датафрейма
    data = []
    mdl_belts_dict = ktkz.mdl_belts_full_dict(mdl)
    # Перебираем каждый элемент в prot_work
    for prot_id, prot in prot_work.items():
        # Достаем соответствующий элемент из submdl_dict
        submdl = submdl_dict[prot['submdl_id']]
        
        # Достаем соответствующий объект защиты из mdl.bd
        if prot['id'] > 0:
            for d in mdl.bd:
                if d.stat_id == prot['id']:  
                    prot_bd = d
            if submdl['line_kz'] == prot_bd.p.name:
                belt = 0
            else:
                line_kz_obj = ktkz.p_search(mdl,p_name=submdl['line_kz'])
                belt = mdl_belts_dict[line_kz_obj.name][prot_bd.p.name]
    
            
            # Формируем строку с нужными данными
            row = {
                'line_kz': submdl['line_kz'],
                'kz_type': submdl['kz_type'],
                'percent': submdl['percent'],
                'p_off_submdl': submdl['p_off'],
                'I0_line' : prot['I0_line'],
                'I0_prot': prot_bd.I0,
                't_prot': prot_bd.t,
                'line_prot': prot_bd.p.name,
                'q_prot': prot_bd.q.name,
                'prot_stage': prot_bd.stage,
                'p_off_prot_work': prot['p_off'],
                't_work': prot['t'],
                'k_ch': prot['k_ch'],
                'prot_work_id': prot_id,
                'belt': belt
            }
        else:
            if prot['id'] == -7:
                text = 'Линия отключена'
            elif prot['id'] == -666:
                text = 'Защиты не сработали'
                #print(text, prot_id)
            # Формируем строку с нужными данными
            row = {
                'line_kz': submdl['line_kz'],
                'kz_type': submdl['kz_type'],
                'percent': submdl['percent'],
                'p_off_submdl': submdl['p_off'],
                'I0_line': prot['I0_line'],
                'I0_prot': 0,
                't_prot': 0,
                'line_prot': text,
                'q_prot': '',
                'prot_stage': '',
                'p_off_prot_work': prot['p_off'],
                't_work': prot['t'],
                'k_ch': prot['k_ch'],
                'prot_work_id': prot_id,
                'belt': belt
            }
            #print(row)
        # Добавляем строку в список
        data.append(row)
    
    # Преобразуем список строк в датафрейм
    df = pd.DataFrame(data)
    return df
#df = prot_work_df(mdl, prot_work, submdl_dict)
# Выводим результат
#df.loc[(df['line_prot']=='Защиты не сработали')]#['line_kz'].unique()
#df.head()

'''
Бэкап функции 22.09, удалить, если все будет норм работать
def def_score(mdl,prot_work, no_off=10, off=-1, non_select=1, k_loss_time=10, k_loss_k_ch=10, show_result=True, range_prot_analyse=False): 
        if range_prot_analyse: r=2
        else:                  r=1        
        select_count = 0
        non_select_count = 0    
        loss = 0
        total_time = 0
        time_count = 0
        k_ch_count = 0
        total_k_ch = 0
        no_off_count = 0
        try: del mdl_belts_dict 
        except: 1
        mdl_belts_dict = ktkz.mdl_belts_full_dict(mdl)
        for work_id in prot_work:
            work = prot_work[work_id]
            
            if work['id'] == -666:
                loss += no_off
                no_off_count += 1
            elif work['id'] == -7:
                loss += off
                total_time += work['t']
                time_count += 1
            else:
                #print(work['line_kz'],work['line'])
                if work['line_kz'] == work['line']:
                    belt = 0
                else:
                    belt = mdl_belts_dict[work['line_kz']][work['line']]
                    
                if belt >= r:
                    loss += non_select
                    non_select_count += 1
                else:
                   k_ch_count += 1
                   #total_k_ch +=  
                   select_count +=1
                    
        try: mean_time = total_time/time_count
        except: mean_time = 1000
        try: mean_k_ch = total_k_ch/k_ch_count
        except: mean_k_ch = 1000
        #loss += mean_time * k_loss_time
        #loss -= mean_k_ch * k_loss_k_ch
        
        if show_result: print(f'Общая ошибка: {loss}\nКоличество неселективных срабатываний: {non_select_count}\nКоличество селективных срабатываний: {select_count}\nКоличество неотключений: {no_off_count}\nСреднее время отключения: {mean_time}')#\nСредний Кч:{mean_k_ch}')
        return loss
'''

def def_score(mdl,prot_work, no_off=10, off=-1, non_select=1, k_loss_time=10, k_loss_k_ch=10, show_result=True, range_prot_analyse=False, is_loss_by_lines=False, is_loss_by_prot=False, extended_result=False): 
        if range_prot_analyse: r=2
        else:                  r=1        
        select_count = 0
        non_select_count = 0    
        loss = 0
        total_time = 0
        time_count = 0
        k_ch_count = 0
        total_k_ch = 0
        no_off_count = 0
        try: del mdl_belts_dict 
        except: 1
        mdl_belts_dict = ktkz.mdl_belts_full_dict(mdl, is_name=True)
        if is_loss_by_lines: 
            loss_by_lines = {}       #{'line1':{[non_select_int_value,non_off_int_value]},'line2':{[non_select_int_value,non_off_int_value]}, ...} 
            for p in mdl.bp:
                loss_by_lines[p.name] = [0, 0]
        if is_loss_by_prot: 
            loss_by_prot= {}         #{'prot1':{[non_select_int_value,select_int_value], k_ch_min, k_ch_max},'prot2':{[non_select_int_value,select__int_value]}, ...} 
            for d in mdl.bd:
                loss_by_prot[d.stat_id] = [0, 0]
        for work_id in prot_work:
            work = prot_work[work_id]
            
            if work['id'] == -666:
                loss += no_off
                no_off_count += 1
                if is_loss_by_lines: loss_by_lines[work['line_kz']][1] += 1

            elif work['id'] == -7:
                loss += off
                total_time += work['t']
                time_count += 1
            else:
                #print(work['line_kz'],work['line'])
                if work['line'] in ['kz-q2','q1-kz', work['line_kz']]:
                    work_line = work['line_kz']
                    belt = 0
                else:
                    work_line = work['line']
                    try: belt = mdl_belts_dict[work['line_kz']][work_line]
                    except: belt = 4
                if belt >= r:
                    loss += non_select*belt
                    non_select_count += 1
                    if is_loss_by_lines: loss_by_lines[work['line_kz']][0] += 1
                    if is_loss_by_prot: 
                        loss_by_prot[work['id']][0] +=1
                else:
                   k_ch_count += 1
                   #total_k_ch +=  
                   select_count +=1
                   if is_loss_by_prot: 
                        loss_by_prot[work['id']][1] +=1
                    
                    
        try: mean_time = total_time/time_count
        except: mean_time = 1000
        try: mean_k_ch = total_k_ch/k_ch_count
        except: mean_k_ch = 1000
        #loss += mean_time * k_loss_time
        #loss -= mean_k_ch * k_loss_k_ch
        try: select_share = non_select_count*100/(non_select_count+select_count)
        except: select_share = 0
        if show_result: print(f'Общая ошибка: {loss}\nКоличество неселективных срабатываний: {non_select_count}\nКоличество селективных срабатываний: {select_count}\nДоля селективных срабатываний:{select_share}%\nКоличество неотключений: {no_off_count}\nСреднее время отключения: {mean_time}')#\nСредний Кч:{mean_k_ch}')
        if extended_result:
            return {'loss':loss, 'non_select_count':non_select_count, 'select_count': select_count, 'select_share': select_share, 'no_off_count': no_off_count, 'mean_time': mean_time}
        elif not (is_loss_by_prot and is_loss_by_lines):
            return loss
        else:
            if not is_loss_by_prot:
                return loss, loss_by_lines
            elif not is_loss_by_lines:
                return loss, loss_by_prot
            else:
                return loss, loss_by_lines, loss_by_prot
        

'''
Основная функция
'''
def ML_func(mdl, submdl_dict, new_settings_dict='', range_prot_analyse=False, show_result=False, no_off=10, off=0, non_select=1, k_loss_time=5, k_loss_k_ch=0, no_off_dist=5, off_dist=0, non_select_dist=0.3, k_loss_time_dist=0.2, k_loss_k_ch_dist=0, extended_result=False):
    if new_settings_dict!='':    
        for prot_id in new_settings_dict['I0_сраб'].keys():
            new_I0 = int(new_settings_dict['I0_сраб'][prot_id])
            new_t = new_settings_dict['t_сраб'][prot_id]
            mdl.bd[int(prot_id-1)].edit(I0=new_I0, t=new_t)
    
    prot_work = analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False)
    loss = def_score(mdl,prot_work=prot_work, no_off=no_off, off=off, non_select=non_select, k_loss_time=k_loss_time, k_loss_k_ch=k_loss_k_ch, show_result=show_result, extended_result=extended_result)
    # если анализируется дальнее резервирование
    if range_prot_analyse: 
        dist_prot_work = analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=True)
        dist_loss = def_score(mdl, prot_work=dist_prot_work, no_off=dist_no_off, off=dist_off, non_select=dist_non_select, k_loss_time=dist_k_loss_time, k_loss_k_ch=dist_k_loss_k_ch, show_result=dist_show_result, range_prot_analyse=True)
        loss += dist_loss
    return loss


'''
Пример уставок
'''
def test_settings_dict():
    settings_dict = {'I0_сраб': {5.0: 4976.4410516739545, 6.0: 3191.308948015621, 7.0: 4830.1589704494045, 8.0: 3034.28693855335, 9.0: 2313.8948589784995, 11.0: 4121.164818380947, 13.0: 3324.3128454685484, 15.0: 3362.946639336927, 10.0: 4370.383849239626, 12.0: 4710.318435030866, 14.0: 848.6619720830896, 16.0: 3249.848370224243, 17.0: 3703.12494235752, 19.0: 2621.407107097972, 21.0: 4873.4887192220785, 23.0: 3215.470387809588, 18.0: 2772.7403953722605, 20.0: 2176.800132530453, 22.0: 4038.88462264361, 24.0: 2803.1972419871227, 25.0: 3436.0583705859094, 27.0: 4979.945377580756, 29.0: 183.4011229449245, 31.0: 4188.559418992118, 26.0: 3679.665940791303, 28.0: 4169.557871892137, 30.0: 2293.5570878092494, 32.0: 1736.0241188373398, 33.0: 1297.612044097331, 35.0: 1417.3703308457352, 37.0: 1629.644674092039, 39.0: 3346.9189855710465, 34.0: 1533.7710284369539, 36.0: 4111.829599696562, 38.0: 32.40746825480589, 40.0: 3855.1530006578328, 41.0: 1607.2699276663138, 43.0: 4681.725225321976, 45.0: 3671.319582114711, 47.0: 477.101062989479, 42.0: 962.0928710346616, 44.0: 32.610324326726726, 46.0: 2746.9563195875185, 48.0: 3705.597546401488, 69.0: 2680.247925541588, 49.0: 2292.8575658188083, 51.0: 2447.9255890586555, 53.0: 1683.1465790337468, 55.0: 3005.2505609823875, 50.0: 3867.925975462709, 52.0: 2005.3063406066558, 54.0: 3235.9075284418127, 56.0: 2343.955122093346, 57.0: 3954.7832689699, 58.0: 1709.6431949706775, 59.0: 3434.891159324995, 60.0: 2380.1102765553105, 61.0: 3583.168362937365, 62.0: 3662.041947101575, 63.0: 4378.959865421181, 64.0: 809.9708428108693, 65.0: 4680.132591952759, 66.0: 3784.9987185159684, 67.0: 3379.301686368583, 68.0: 2019.606240207515, 1.0: 3810.95770568832, 2.0: 3489.4650121479144, 3.0: 2388.378853956322, 4.0: 4588.623641294481}, 't_сраб': {5.0: 1.1163429442725343, 6.0: 2.3363764667946545, 7.0: 0.7760641695537246, 8.0: 1.0546142015456694, 9.0: 2.3443074264331325, 11.0: 3.0061512111354904, 13.0: 0.7010254009706596, 15.0: 0.6813927058456415, 10.0: 3.1909920353357615, 12.0: 1.8263277270392826, 14.0: 3.208611405419485, 16.0: 2.4877438337470203, 17.0: 3.5096607956812753, 19.0: 0.2683890292921759, 21.0: 3.2387372043208593, 23.0: 4.440020156188095, 18.0: 0.2894607972801133, 20.0: 2.2675864721966095, 22.0: 4.487243525166956, 24.0: 2.8681008638852816, 25.0: 0.6565181220735011, 27.0: 3.478627022756056, 29.0: 1.575224472010746, 31.0: 1.7275358594299162, 26.0: 3.2482637344650915, 28.0: 1.4844818406730032, 30.0: 2.2202759813938404, 32.0: 4.253931205661342, 33.0: 0.919831723511631, 35.0: 2.0805861145660156, 37.0: 0.7425346045369619, 39.0: 1.8007263667108249, 34.0: 2.490165246732843, 36.0: 0.6837865757399486, 38.0: 2.7431975748746638, 40.0: 2.560310196172903, 41.0: 2.480435748917053, 43.0: 1.403550106769017, 45.0: 3.2828972457373147, 47.0: 3.1311797727691033, 42.0: 1.270093073150128, 44.0: 4.916774471913408, 46.0: 4.99684018374227, 48.0: 1.8203402909867288, 69.0: 1.4806377782229534, 49.0: 2.7086716143465677, 51.0: 1.9121126973703055, 53.0: 4.63263352805131, 55.0: 1.0807183130436222, 50.0: 2.44741278778823, 52.0: 4.997874485051252, 54.0: 4.46378064880183, 56.0: 2.4983162788631303, 57.0: 1.3076329194187908, 58.0: 1.8380352775404618, 59.0: 1.4820335403170148, 60.0: 2.028073098005822, 61.0: 2.4908667882207247, 62.0: 4.974831508204851, 63.0: 4.410275732515502, 64.0: 3.9668068870141755, 65.0: 4.67672473515071, 66.0: 0.37874793078801483, 67.0: 3.9748554027293643, 68.0: 1.253744086349669, 1.0: 1.1638931346970438, 2.0: 4.212344207909008, 3.0: 4.794963173987856, 4.0: 0.816758633305737}}

    return settings_dict



# записывает уставки из модели в словарь, если pq, то вместе с объектами p,q
def set_to_dict(mdl, pq=False):
    set_dict = {}
    for prot in mdl.bd:
        if pq: set_dict[prot.stat_id] = {'I0_сраб':prot.I0, 't_сраб':prot.t, 'line':prot.p.name, 'q':prot.q.name, 'stage':prot.stage}
        else: set_dict[prot.stat_id] = {'I0_сраб':prot.I0, 't_сраб':prot.t}
    return set_dict
    
# преобразует словарь уставок в изменение модели
def dict_to_set(mdl, set_dict, id_version = True):
    # для словаря фотамата {prot_id:['I0_сраб','t_сраб']
    if id_version:
        for prot_id in set_dict:
            new_I0 = int(set_dict[prot_id]['I0_сраб'])
            new_t = set_dict[prot_id]['t_сраб']
            mdl.bd[int(prot_id-1)].edit(I0=new_I0, t=new_t)
    # для словаря фотамата {'I0_сраб':[I01,I02...],'t_сраб':[t1,t2...]]
    else:       
        for prot_id in set_dict:
            new_I0 = int(set_dict['I0_сраб'][prot_id])
            new_t = set_dict['t_сраб'][prot_id]
            mdl.bd[int(prot_id-1)].edit(I0=new_I0, t=new_t)
    return mdl





def vis_relay_protection_work(mdl, submdl_raw, range_prot_analyse=False):
    def vis_I0_graph(mdl):
        mdl.Calc()
        G = mdl.G
        label_dict = {}
        for p in mdl.bp:
            if p.q1!=0: q1_name = p.q1.name
            else:       q1_name = p.name+'_0'
                
            if p.q2!=0: q2_name = p.q2.name
            else:       q2_name = p.name+'_0'
                
            I0 = p.res1(['I0'], 'M')['I0']
            ang = p.res1(['I0'], '<f')['I0']
            if ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                way = '->'
            else:
                way= '<-'
            line_label = q1_name + way + q2_name + '\n' + 'I0=' + str(round(I0))
            #line_label += '\n'+str(p.Z[2])
            #print(line_label)
            for pg in mdl.G.edges:
                if (q1_name, q2_name) == pg or (q2_name, q1_name) == pg: 
                    line_g = pg
            # Добавление лейбла к конкретному ребру
            label_dict[line_g] = line_label
        
        
        #print(label_dict)   
        nx.set_edge_attributes(G, label_dict, 'label')
        pos = nx.get_node_attributes(mdl.G, 'pos')
        
        nx.draw(mdl.G, pos, with_labels=True, node_color='lightblue', node_size=500, font_size=10, font_weight='bold')
        edge_labels = nx.get_edge_attributes(mdl.G, 'label')
        nx.draw_networkx_edge_labels(mdl.G, pos, edge_labels=edge_labels, font_size=8, bbox=dict(boxstyle="round",pad=0, edgecolor='none', alpha=0))
        
        plt.title("Участок энергосистемы")
        plt.axis('off')
        plt.show()
    
    # Функция для анализа отключений релейной защиты. Возвращает словарь с данными отключения
    def vis_analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False):
        """
        Функция для анализа отключений релейной защиты.
    
        Аргументы:
        mdl -- основная модель системы
        submdl_dict -- словарь подмоделей с информацией о линиях, процентах отключений и типах КЗ
        log -- флаг для вывода логов (по умолчанию False)
        range_prot_analyse - флаг для выбора рассчетов ближнего или дальнего резервирования False
        
        Возвращает:
        off_result -- словарь с результатами отключений
        """
        # Засекаем начальное время
        t1 = time.time()
        cut_id = 0
        off_result = {}  # Результаты отключений
        base_t_dict = {}  # Словарь для хранения времени срабатывания защит
    
        # Сохраняем базовое время защит для каждой защиты в модели
        for d in mdl.bd:
            base_t_dict[d.stat_id] = d.t
        # Проходим по каждому элементу в подмоделях
        for submdl_id in submdl_dict:
    
            # Извлекаем данные для текущей подмодели
            line = submdl_dict[submdl_id]['line_kz']
            percent = submdl_dict[submdl_id]['percent']
            p_off = submdl_dict[submdl_id]['p_off']
            kz_type = submdl_dict[submdl_id]['kz_type']
            
            # Поиск линии по имени
            line_obj = ktkz.p_search(mdl, p_name=line)
            
            # Создаем подмодель с учётом процента линии и типа КЗ
            submdl = ktkz.kz_q(mdl, line=line_obj, percentage_of_line=percent, show_G=False, show_par=False, kaskade=False)
            
            # Удаление мощности для подмодели на определённой поясной зоне
            submdl = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False, node = False)#submdl.bq[-1].name)
            
            # Расчёт КЗ для подмодели
            KZ1 = mrtkz.N(submdl, 'KZ', submdl.bq[-1], kz_type)
            
            # Выполняем расчёт для подмодели
            submdl.Calc()
            
            t=0
            p_off = ()
            t_dict = base_t_dict
            t_total = 0
            while True:
                # Пересчёт подмодели с новыми условиями
                submdl_temp = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False)
                submdl_temp.Calc()
                vis_I0_graph(submdl_temp)
    
                # Проверяем, отключилось ли КЗ
                try: 
                    I0_kz = submdl_temp.bn[0].res('I0', 'M') # если узел кз исчез, значит удалили все ветви вокруг, КЗ отключено
                    #print('Ток в точке КЗ',submdl_temp.bn[0].res('I0', 'M'))
                except: 
                    off_result_row = {'id': -7, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.name, 'line': 0, 'I0_line': I0_kz}   
                    off_result[cut_id] = off_result_row  # Добавление отключения в общий результат
                    cut_id+=1
                    break
                if not I0_kz>10:
                    off_result_row = {'id': -7, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.name, 'line': 0, 'I0_line': I0_kz}   
                    off_result[cut_id] = off_result_row  # Добавление отключения в общий результат
                    cut_id+=1
                    break
    
                # Поиск защит, которые чувствуют КЗ
                prot_dict = {}
                for p in submdl_temp.bp:
                    I0 = p.res1(['I0'], 'M')['I0']
                    ang = p.res1(['I0'], '<f')['I0']
                    for d1 in p.q1_def:
                        if I0 >= d1.I0 and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                            print(round(I0), '>', d1.I0)
                            print(p.name,d1.t, 'q1')
                            did = d1.stat_id
                            try: k_ch = d1.I0 / I0
                            except: k_ch = 0
                            
                            prot_dict[did] = {'id': did, 'line': d1.p.name, 't': t_dict[did], 'k_ch': k_ch}
                    for d2 in p.q2_def:
                        if I0 >= d2.I0 and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                            print(round(I0), '>', d2.I0)
                            print(p.name,d2.t,'q2')
                            did = d2.stat_id
                            try: k_ch = d1.I0 / I0
                            except: k_ch = 0
                            prot_dict[did] = {'id': did, 'line': d2.p.name, 't': t_dict[did], 'k_ch': k_ch}
    
                # Если ни одна защита не сработала
                if prot_dict == {}:
                    off_result_row = {'id': -666, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': 0, 'line_kz':line_obj.name, 'line': 0, 'I0_line': I0_kz}   
                    off_result[cut_id] = off_result_row  # Добавление результата в общий словарь
                    cut_id += 1
                    
                    break
    
                # Обрабатываем сработавшие защиты
                prot_worked = False
                # находим защиту с мин временем срабатывания
                temp_t_list=[]
                t=0
                for p_id in prot_dict:
                    temp_t_list += [prot_dict[p_id]['t']]
                t = min(temp_t_list)
                t_total += t
                #print(t)
                for p_id in prot_dict:
                    if prot_dict[p_id]['line'] in p_off or (range_prot_analyse and prot_dict[p_id]['line'] == line):
                        continue
    
    
                    else:
                        if t_dict[p_id] == t:
                            off_result_row = {'id': p_id, 't': t_total, 'submdl_id': submdl_id, 'p_off': p_off, 'k_ch': prot_dict[p_id]['k_ch'], 'line_kz':line_obj.name, 'line': prot_dict[p_id]['line'], 'I0_line': I0_kz}   
                            off_result[cut_id] = off_result_row  # Добавление в результат
                            cut_id += 1
                            p_off = p_off + (prot_dict[p_id]['line'],)
                            #print(off_result_row)
                        else:
                            t_dict[p_id] -= t
        #prot_dict[p_id]['t']
        # Засекаем конечное время и выводим время анализа, если включен лог
        t2 = time.time()
        if log:
            print(f"Время анализа: {t2 - t1} секунд")
    
        return off_result
        vis_analyze_relay_protections(mdl, submdl_dict,range_prot_analyse)

def to_submdl(mdl, submdl_dict_row):  
    # Извлекаем данные для текущей подмодели
    line = submdl_dict_row['line_kz']
    percent = submdl_dict_row['percent']
    p_off = submdl_dict_row['p_off']
    kz_type = submdl_dict_row['kz_type']
    
    # Поиск линии по имени
    line_obj = ktkz.p_search(mdl, p_name=line)
    
    # Создаем подмодель с учётом процента линии и типа КЗ
    submdl = ktkz.kz_q(mdl, line=line_obj, percentage_of_line=percent, show_G=False, show_par=False, kaskade=False)
    
    # Удаление мощности для подмодели на определённой поясной зоне
    submdl = ktkz.p_del(submdl, del_p_name=p_off, show_G=False, show_par=False, node = False)
    
    # Расчёт КЗ для подмодели
    KZ1 = mrtkz.N(submdl, 'KZ', submdl.bq[-1], kz_type)
    
    # Выполняем расчёт для подмодели
    submdl.Calc()
    return submdl



# визуализирует отключение
def show_bad_submdls(mdl, submdl_dict, non_off=True, non_select=True, show_dict=False):
    prot_work = kanl.analyze_relay_protections(mdl, submdl_dict)
    non_select_dict = {}
    non_off_dict = {}

    for work_id in prot_work:
        work = prot_work[work_id]
        if work['id']==-666:
            non_off_dict[work['submdl_id']] = submdl_dict[work['submdl_id']]
            
        if not work['line'] in ['q1-kz', 'kz-q2', 0]:
            non_select_dict[work['submdl_id']] = submdl_dict[work['submdl_id']]
    if show_dict:
        print(non_select_dict)
        print(non_off_dict)
    if non_off:
        print('Начат анализ режимов где защиты не чувствуют КЗ:\n\n\n')
        kanl.analyze_relay_protections(mdl, non_off_dict, print_G=True)
        
    if non_select:
        print('Начат анализ неселективных режимов:\n\n\n')
        kanl.analyze_relay_protections(mdl, non_select_dict, print_G=True)






#@@@@@@@@@@@@@@@@@@@@@@@@@@_________КАЛЬКУЛЯТОР ПОДРЕЖИМОВ_________@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

def tokenize_expression(expression):
    """
    Разбивает выражение на токены, поддерживая многоуровневые скобки.
    """
    tokens = []
    current_token = ''
    bracket_level = 0
    
    for char in expression:
        if char == '(' and bracket_level == 0:
            if current_token:
                tokens.append(current_token)
                current_token = ''
            bracket_level += 1
            current_token += char
        elif char == ')' and bracket_level > 0:
            current_token += char
            bracket_level -= 1
            if bracket_level == 0:
                tokens.append(current_token)
                current_token = ''
        elif char in ('*', '+') and bracket_level == 0:
            if current_token:
                tokens.append(current_token)
            tokens.append(char)
            current_token = ''
        else:
            current_token += char
            if char == '(':
                bracket_level += 1
            elif char == ')':
                bracket_level -= 1
    
    if current_token:
        tokens.append(current_token)
    
    return tokens

def separate_by_plas(expression):
    tokens = tokenize_expression(expression)
    global_list = []
    current_list = []
    for token in tokens:
        if token== '+': 
            global_list.append(current_list)
            current_list = []
        elif token=='*': continue
        else: current_list.append(token)
    global_list.append(current_list)
    current_list = []
    return global_list


def parse(item):
    # Удаляем пробелы
    item = item.strip()
    # Проверяем, является ли это функцией с аргументами в квадратных скобках
    if '[' in item and ']' in item:
        function_name, args_str = item.split('[', 1)
        args_str = args_str.rstrip(']')
        args = [arg.strip() for arg in args_str.split(',')]
        func = function_name.strip().upper()
        return func, args
    else:
        func = item.strip().upper()
        args = []
        # Функция без аргументов
        return func, args
    
def enum_biggest_I(mdl, line_kz, kz_types, n):
    I0_dict = {}
    line_obj = ktkz.p_search(mdl, p_name=line_kz)
    mdl = ktkz.kz_q(mdl, line=line_obj, percentage_of_line=0.5, show_G=False)
    kz_type = kz_types[0]
    smdl = ktkz.duplicate_mdl(mdl)
    mrtkz.N(smdl,'KZ', smdl.bq[-1], kz_type)
    smdl.Calc()
    for p in smdl.bq[-1].plist:
        if p.name=='q1-kz':
            for p_q1 in p.q1.plist:
                if p_q1!=p:
                    I0_dict[p_q1.name] = p_q1.res1(['I0'],'M')
        else:
            for p_q2 in p.q2.plist:
                if p_q2!=p:
                    I0_dict[p_q2.name] = p_q2.res1(['I0'],'M')
    lines_list = []
    for i in range(0, n):
        I_max = 0
        for p_name in I0_dict:
            if I0_dict[p_name]['I0'] > I_max:
                I_max = I0_dict[p_name]['I0']
                line_max = p_name
        lines_list.append(line_max)
        I0_dict[line_max]['I0'] = 0
    return tuple(set(lines_list))


def induct(mdl, line_kz):
    p_off = ()
    line_obj = ktkz.p_search(mdl, p_name=line_kz)
    for m in mdl.bm:
        if m.p1==line_obj: p_off += (m.p2.name,)
        elif m.p2==line_obj: p_off += (m.p1.name,)
    return p_off
    
def belt(mdl, belt, line):
    # функция вызывающаяся через ПОЯС[int]
    line_obj = ktkz.p_search(mdl, p_name=line)
    p_off = ()
    if type(belt)!= list: belt = [belt]
    for b in belt:
        b = int(b)
        p_off += tuple(ktkz.belt_search(mdl=mdl, line=line_obj, n=b, return_names=True)[0][b])
    return p_off

def find_const_in_buscets(string, m, lines_kz, step, kz_types, mdl):
    # функция находит сумму констант одного типа, если они находятся в скобках   
    if '*' in string:
        return m, lines_kz, step
    else:
        if string.startswith('(') and string.endswith(')'):
            # Удаляем первую и последнюю скобку
            string = string[1:-1]
        list = separate_by_plas(string)
        for items in list:
            for item in items:
                func, arg = parse(item)
                if func=="ПЕРЕБОР": m=arg
                elif func=='ЛИНИИКЗ': 
                    if arg==['ВСЕ']:
                        arg = [p.name for p in mdl.bp]
                    lines_kz = tuple(arg)
                elif func=='ШАГ': step = arg
                elif func=='ТИПКЗ': kz_types = arg
    return m, lines_kz, step, kz_types

def find_p_off_summ_in_buscets(string, m, lines_kz, step, kz_types, mdl, submdl_dict, log=False):
    # функция находит сумму линий отключения, если они записанны суммой в скобках и вычисляет для них подмодели    
    if '*' in string:
        return submdl_dict
    else:
        if string.startswith('(') and string.endswith(')'):
            # Удаляем первую и последнюю скобку
            string = string[1:-1]
        #print(string)
        list = separate_by_plas(string)
        test,_ = parse(list[0][0])
        #print('test',test)
        if not test in  ["ИНДУКЦ", "ПОЯС", "ОБЪЕКТЫ", "МАКСТОК"]:
            return submdl_dict
        for line_kz in lines_kz:
            p_off = ()
            for items in list:
                for item in items:
                    #print('ccc',item)
                    func, arg = parse(item)
                    #print('cbc',func, arg)
                    if func=="ИНДУКЦ": p_off += induct(mdl, line_kz)
                    elif func=="ПОЯС":
                        p_off += belt(mdl, line=line_kz, belt=arg)
                    elif func=="МАКСТОК":
                        p_off += enum_biggest_I(mdl, line_kz, kz_types, n=int(arg[0])) 
                    elif func=="ОБЪЕКТЫ":
                        #print('cbb',arg)
                        p_off += tuple(arg)
            #print(p_off)
            p_off = tuple(set(p_off))
            if log: print( f'Перебор:{m}, Линия кз:{line_kz}, Шаг:{step}, откл линии:{p_off}, Типы кз:{kz_types}')
            submdl_dict = base_func(mdl, m, line_kz, step, p_off, kz_types, submdl_dict)
        return submdl_dict

  
def base_func(mdl, m, line_kz, step, p_off, kz_types, submdl_dict, log=False):
    try:
        id = max([idn for idn in submdl_dict])
    except: id=0
    #print(id, m, line_kz, step, p_off, kz_types)
    # Генерация списка вариантов отключений
    p_off_dict = {}
    p_off_dict[0] = p_off
    if type(m)!=list:   m = [m]
    p_off_list = []
    for one_m in m:
        one_m = int(one_m)
        p_off_list += ktkz.generate_line_combinations(p_range_dict=p_off_dict, m=one_m, show_info=False, return_as_list=False, belts_list = '')
    # Перебор вариантов отключений
    for p_off in p_off_list:
        # Перебор процентного значения (0% до 100%) с заданным шагом
        for percent in range(0, 101, int(step * 100)):   
            perc = percent/100
            # Перебор типов короткого замыкания
            for kz_type in kz_types:
                id += 1  # Увеличение счетчика ID
                
                # Создание строки данных для текущеq подмоделb
                submdl_row = {'id': id, 'line_kz': line_kz, 'kz_type': kz_type, 'percent': perc, 'p_off': p_off}
                
                
                # Добавление текущего режима в общий словарь
                submdl_dict[id] = submdl_row  # Добавляем строку с данными в словарь
    return submdl_dict

def submdl_calc_main(mdl, task_str, submdl_dict={}, m=0, lines_kz=[], step=0, p_off=(), kz_types=[], log=False):
    string = task_str
    # делим строку по слогаемым
    sum_list = separate_by_plas(string)
    # начинаем анализ одного слогаемого
    for sum_item in sum_list:
        for item in sum_item:
            #print(item)
            if "(" in item: 
                m, lines_kz, step = find_const_in_buscets(string, m, lines_kz, step, kz_types, mdl)
            
            else:
                func, arg = parse(item)
                if func=="ПЕРЕБОР": 
                    m=arg
                elif func=='ЛИНИИКЗ': 
                    if arg==['ВСЕ']:
                        arg = [p.name for p in mdl.bp]
                    lines_kz = arg
                elif func=='ШАГ': step = float(arg[0]) 
                elif func=='ТИПКЗ': kz_types = arg
        #if log: print("Константы" ,m, lines_kz, step, p_off, kz_types)
        for item in sum_item: 
            func, arg = parse(item)
            if func == "ИНДУКЦ":
                for line_kz in lines_kz:
                    p_off = induct(mdl, line_kz)
                    if log: print( f'Перебор:{m}, Линия кз:{line_kz}, Шаг:{step}, откл линии:{p_off}, Типы кз:{kz_types}')
                    submdl_dict = base_func(mdl, m, line_kz, step, p_off, kz_types, submdl_dict)  
            elif func == "ПОЯС":
                for line_kz in lines_kz:
                    p_off += belt(mdl, line=line_kz, belt=arg)  
                    if log: print( f'Перебор:{m}, Линия кз:{line_kz}, Шаг:{step}, откл линии:{p_off}, Типы кз:{kz_types}')
                    submdl_dict = base_func(mdl, m, line_kz, step, p_off, kz_types, submdl_dict)
            elif func == "МАКСТОК":
                for line_kz in lines_kz:
                    p_off += enum_biggest_I(mdl, line_kz, kz_types, n=int(arg[0])) 
                    if log: print( f'Перебор:{m}, Линия кз:{line_kz}, Шаг:{step}, откл линии:{p_off}, Типы кз:{kz_types}')
                    submdl_dict = base_func(mdl, m, line_kz, step, p_off, kz_types, submdl_dict)
            elif func == "ОБЪЕКТЫ":
                for line_kz in lines_kz:
                    p_off += tuple(arg)
                    if log: print( f'Перебор:{m}, Линия кз:{line_kz}, Шаг:{step}, откл линии:{p_off}, Типы кз:{kz_types}')
                    submdl_dict = base_func(mdl, m, line_kz, step, p_off, kz_types, submdl_dict) 
            elif item.startswith('(') and item.endswith(')'):
                #print('Попытка найти отключенные линии в скобках')
                submdl_dict = find_p_off_summ_in_buscets(item, m, lines_kz=lines_kz, step=step, kz_types=kz_types, mdl=mdl, submdl_dict=submdl_dict, log=log)
        for item in sum_item: 
            if item.startswith('(') and item.endswith(')'):
                if '*' in item:
                    # Удаляем первую и последнюю скобку
                    item = item[1:-1]
                    submdl_dict = submdl_calc_main(mdl, item, submdl_dict, m, lines_kz, step, p_off, kz_types, log=log)
                else: continue
            else: continue
    return submdl_dict
                    
            
# применение
#mdl = ktkz.base_model()
#task_str = "(ПОЯС[2] + ИНДУКЦ + ОБЪЕКТЫ[PS1-PS2, PS2-PS3])*ЛИНИИКЗ[PS1-PS3, PS1-PS2]*ПЕРЕБОР[1]*ТИПКЗ[A0,AB0]*ШАГ[0.2]"
#task_str = "((ИНДУКЦ + ОБЪЕКТЫ[PS1-PS2, PS2-PS3] + МАКСТОК[2])*ЛИНИИКЗ[PS1-PS3, PS1-PS2]*ПЕРЕБОР[1]*ТИПКЗ[A0,AB0]+ПОЯС[1]*ЛИНИИКЗ[PS1-PS3]*ПЕРЕБОР[1]*ТИПКЗ[AB0])*ШАГ[0.4]"
#submdl_dict = submdl_calc_main(mdl, task_str, submdl_dict, m, lines_kz, step, p_off, kz_types, log=True)