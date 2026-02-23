'''
kar_analyse.py — функции анализа срабатывания релейных защит и генерации подрежимов.

Основные группы функций:
  - Генерация подрежимов КЗ: generate_submodels, generate_submodels_one_line
  - Анализ срабатывания защит: analyze_relay_protections
  - Оценка качества уставок: def_score, ML_func
  - Утилиты для работы с уставками: set_to_dict, dict_to_set, to_submdl
  - DSL-калькулятор подрежимов: submdl_calc_main и вспомогательные функции
'''

import kar_mrtkz as ktkz
import mrtkz3 as mrtkz
import time
def generate_submodels_one_line(mdl, line, max_belt_range=2, num_of_enum_lines=1, step=0.05, kz_types=['A0']):
    """
    Генерирует словарь подрежимов КЗ для одной заданной линии.

    Для каждой комбинации поясной зоны отключений, процента расположения
    КЗ на линии и типа КЗ создаёт запись в словаре подрежимов.

    Параметры:
        mdl              -- модель mrtkz.Model
        line             -- объект линии (mrtkz.P), для которой строятся подрежимы
        max_belt_range   -- максимальный пояс перебора отключений (по умолчанию: 2)
        num_of_enum_lines -- количество одновременно отключаемых линий (по умолчанию: 1)
        step             -- шаг по длине линии, доля [0, 1] (по умолчанию: 0.05)
        kz_types         -- список типов КЗ, например ['A0', 'AB0'] (по умолчанию: ['A0'])

    Возвращает:
        dict -- словарь {id: {'id', 'line_kz', 'kz_type', 'percent', 'p_off'}}
    """
    id = 0
    submdl_dict = {}
    p_off_list = ktkz.line_enumiration(mdl, line, max_belt_range=max_belt_range, num_of_enum_lines=num_of_enum_lines,
                                       list_of_belts_for_enum='', return_names=True,
                                       show_info=False, return_as_list=True)

    for p_off in p_off_list:
        for percent in range(0, 100, int(step * 100)):
            perc = percent / 100
            for kz_type in kz_types:
                id += 1
                submdl_row = {'id': id, 'line_kz': line.name, 'kz_type': kz_type, 'percent': perc, 'p_off': p_off}
                submdl_dict[id] = submdl_row
    return submdl_dict



def generate_submodels(mdl, max_belt_range=2, num_of_enum_lines=1, step=0.05, kz_types=['A0']):
    """
    Генерирует словарь подрежимов КЗ для всех линий модели.

    Перебирает все линии в mdl.bp и для каждой строит подрежимы аналогично
    generate_submodels_one_line. Результаты объединяются в единый словарь
    с последовательной нумерацией id.

    Параметры:
        mdl              -- модель mrtkz.Model
        max_belt_range   -- максимальный пояс перебора отключений (по умолчанию: 2)
        num_of_enum_lines -- количество одновременно отключаемых линий (по умолчанию: 1)
        step             -- шаг по длине линии, доля [0, 1] (по умолчанию: 0.05)
        kz_types         -- список типов КЗ (по умолчанию: ['A0'])

    Возвращает:
        dict -- словарь {id: {'id', 'line_kz', 'kz_type', 'percent', 'p_off'}}
    """
    id = 0
    submdl_dict = {}
    for line in mdl.bp:
        p_off_list = ktkz.line_enumiration(mdl, line, max_belt_range=max_belt_range, num_of_enum_lines=num_of_enum_lines,
                                           list_of_belts_for_enum='', return_names=True,
                                           show_info=False, return_as_list=True)

        for p_off in p_off_list:
            for percent in range(0, 100, int(step * 100)):
                perc = percent / 100
                for kz_type in kz_types:
                    id += 1
                    submdl_row = {'id': id, 'line_kz': line.name, 'kz_type': kz_type, 'percent': perc, 'p_off': p_off}
                    submdl_dict[id] = submdl_row
    return submdl_dict


def analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False, print_G=False):
    """
    Симулирует последовательное срабатывание защит для каждого подрежима КЗ.

    Для каждого подрежима из submdl_dict моделирует процесс отключения КЗ:
    итеративно определяет, какая защита сработает первой, отключает
    соответствующую линию и повторяет до полного отключения КЗ.

    Коды результата в поле 'id' записи off_result:
        id > 0   -- защита сработала (id == stat_id защиты)
        id == -7  -- КЗ отключено (нет тока в узле КЗ)
        id == -666 -- ни одна защита не сработала (неотключение)

    Параметры:
        mdl               -- модель mrtkz.Model с настроенными защитами
        submdl_dict       -- словарь подрежимов из generate_submodels
        log               -- если True, выводит время выполнения (по умолчанию: False)
        range_prot_analyse -- если True, исключает из анализа собственную линию КЗ
                             (режим дальнего резервирования) (по умолчанию: False)
        print_G           -- если True, выводит граф сети на каждом шаге (по умолчанию: False)

    Возвращает:
        dict -- off_result {cut_id: {'id', 't', 'submdl_id', 'p_off',
                'k_ch', 'line_kz', 'line', 'I0_line', 'prot_id'}}
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

def def_score(mdl, prot_work, no_off=10, off=-1, non_select=1, k_loss_time=10,
              k_loss_k_ch=10, show_result=True, range_prot_analyse=False,
              is_loss_by_lines=False, is_loss_by_prot=False, extended_result=False):
    """
    Вычисляет значение функции потерь по результатам анализа срабатываний.

    Формула потерь:
        loss = no_off_count × no_off
             + off_count × off
             + Σ (belt × non_select) для неселективных срабатываний

    Параметры:
        mdl               -- модель mrtkz.Model
        prot_work         -- dict из analyze_relay_protections
        no_off            -- штраф за неотключение КЗ (id==-666) (по умолчанию: 10)
        off               -- штраф за нормальное отключение (id==-7) (по умолчанию: -1)
        non_select        -- штраф за неселективность (по умолчанию: 1)
        k_loss_time       -- зарезервировано (по умолчанию: 10)
        k_loss_k_ch       -- зарезервировано (по умолчанию: 10)
        show_result       -- если True, выводит статистику в консоль (по умолчанию: True)
        range_prot_analyse -- если True, учитывает дальнее резервирование (пояс r=2) (по умолчанию: False)
        is_loss_by_lines  -- если True, возвращает потери по линиям (по умолчанию: False)
        is_loss_by_prot   -- если True, возвращает потери по защитам (по умолчанию: False)
        extended_result   -- если True, возвращает расширенный dict вместо числа (по умолчанию: False)

    Возвращает:
        float        -- значение функции потерь (если extended_result=False)
        dict         -- {'loss', 'non_select_count', 'select_count', 'select_share',
                         'no_off_count', 'mean_time'} (если extended_result=True)
        tuple        -- (loss, loss_by_lines) или (loss, loss_by_prot) или
                        (loss, loss_by_lines, loss_by_prot) при is_loss_by_* флагах
    """
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
    

def ML_func(mdl, submdl_dict, new_settings_dict='', range_prot_analyse=False,
            show_result=False, no_off=10, off=0, non_select=1, k_loss_time=5,
            k_loss_k_ch=0, no_off_dist=5, off_dist=0, non_select_dist=0.3,
            k_loss_time_dist=0.2, k_loss_k_ch_dist=0, extended_result=False):
    """
    Вычисляет суммарную функцию потерь для текущих уставок модели.

    Оркестратор: вызывает analyze_relay_protections для получения результатов
    срабатываний, затем def_score для подсчёта потерь. При range_prot_analyse=True
    дополнительно анализирует дальнее резервирование и добавляет его вклад в потери.

    Параметры:
        mdl               -- модель mrtkz.Model
        submdl_dict       -- словарь подрежимов
        new_settings_dict -- если не пустой, применяет уставки до расчёта
                             (формат: {'I0_сраб': {id: I0}, 't_сраб': {id: t}})
        range_prot_analyse -- если True, учитывает дальнее резервирование (по умолчанию: False)
        show_result       -- вывод статистики в консоль (по умолчанию: False)
        no_off            -- штраф за неотключение (по умолчанию: 10)
        off               -- штраф за нормальное отключение (по умолчанию: 0)
        non_select        -- штраф за неселективность (по умолчанию: 1)
        extended_result   -- если True, возвращает расширенный dict (по умолчанию: False)

    Возвращает:
        float или dict -- функция потерь (или расширенный результат при extended_result=True)
    """
    if new_settings_dict != '':    
        for prot_id in new_settings_dict['I0_сраб'].keys():
            new_I0 = int(new_settings_dict['I0_сраб'][prot_id])
            new_t = new_settings_dict['t_сраб'][prot_id]
            mdl.bd[int(prot_id-1)].edit(I0=new_I0, t=new_t)
    
    prot_work = analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=False)
    loss = def_score(mdl,prot_work=prot_work, no_off=no_off, off=off, non_select=non_select, k_loss_time=k_loss_time, k_loss_k_ch=k_loss_k_ch, show_result=show_result, extended_result=extended_result)
    # если анализируется дальнее резервирование
    if range_prot_analyse: 
        dist_prot_work = analyze_relay_protections(mdl, submdl_dict, log=False, range_prot_analyse=True)
        dist_loss = def_score(mdl, prot_work=dist_prot_work, no_off=no_off_dist, off=off_dist, non_select=non_select_dist, k_loss_time=k_loss_time_dist, k_loss_k_ch=k_loss_k_ch_dist, show_result=show_result, range_prot_analyse=True)
        loss += dist_loss
    return loss


def test_settings_dict():
    """
    Возвращает пример словаря уставок для тестирования и отладки.

    Содержит реальные значения I0 и t для 69 защит тестовой модели.
    Используется для воспроизведения конкретного состояния без повторного запуска оптимизации.

    Возвращает:
        dict -- {'I0_сраб': {id: float}, 't_сраб': {id: float}}
    """
    settings_dict = {'I0_сраб': {5.0: 4976.4410516739545, 6.0: 3191.308948015621, 7.0: 4830.1589704494045, 8.0: 3034.28693855335, 9.0: 2313.8948589784995, 11.0: 4121.164818380947, 13.0: 3324.3128454685484, 15.0: 3362.946639336927, 10.0: 4370.383849239626, 12.0: 4710.318435030866, 14.0: 848.6619720830896, 16.0: 3249.848370224243, 17.0: 3703.12494235752, 19.0: 2621.407107097972, 21.0: 4873.4887192220785, 23.0: 3215.470387809588, 18.0: 2772.7403953722605, 20.0: 2176.800132530453, 22.0: 4038.88462264361, 24.0: 2803.1972419871227, 25.0: 3436.0583705859094, 27.0: 4979.945377580756, 29.0: 183.4011229449245, 31.0: 4188.559418992118, 26.0: 3679.665940791303, 28.0: 4169.557871892137, 30.0: 2293.5570878092494, 32.0: 1736.0241188373398, 33.0: 1297.612044097331, 35.0: 1417.3703308457352, 37.0: 1629.644674092039, 39.0: 3346.9189855710465, 34.0: 1533.7710284369539, 36.0: 4111.829599696562, 38.0: 32.40746825480589, 40.0: 3855.1530006578328, 41.0: 1607.2699276663138, 43.0: 4681.725225321976, 45.0: 3671.319582114711, 47.0: 477.101062989479, 42.0: 962.0928710346616, 44.0: 32.610324326726726, 46.0: 2746.9563195875185, 48.0: 3705.597546401488, 69.0: 2680.247925541588, 49.0: 2292.8575658188083, 51.0: 2447.9255890586555, 53.0: 1683.1465790337468, 55.0: 3005.2505609823875, 50.0: 3867.925975462709, 52.0: 2005.3063406066558, 54.0: 3235.9075284418127, 56.0: 2343.955122093346, 57.0: 3954.7832689699, 58.0: 1709.6431949706775, 59.0: 3434.891159324995, 60.0: 2380.1102765553105, 61.0: 3583.168362937365, 62.0: 3662.041947101575, 63.0: 4378.959865421181, 64.0: 809.9708428108693, 65.0: 4680.132591952759, 66.0: 3784.9987185159684, 67.0: 3379.301686368583, 68.0: 2019.606240207515, 1.0: 3810.95770568832, 2.0: 3489.4650121479144, 3.0: 2388.378853956322, 4.0: 4588.623641294481}, 't_сраб': {5.0: 1.1163429442725343, 6.0: 2.3363764667946545, 7.0: 0.7760641695537246, 8.0: 1.0546142015456694, 9.0: 2.3443074264331325, 11.0: 3.0061512111354904, 13.0: 0.7010254009706596, 15.0: 0.6813927058456415, 10.0: 3.1909920353357615, 12.0: 1.8263277270392826, 14.0: 3.208611405419485, 16.0: 2.4877438337470203, 17.0: 3.5096607956812753, 19.0: 0.2683890292921759, 21.0: 3.2387372043208593, 23.0: 4.440020156188095, 18.0: 0.2894607972801133, 20.0: 2.2675864721966095, 22.0: 4.487243525166956, 24.0: 2.8681008638852816, 25.0: 0.6565181220735011, 27.0: 3.478627022756056, 29.0: 1.575224472010746, 31.0: 1.7275358594299162, 26.0: 3.2482637344650915, 28.0: 1.4844818406730032, 30.0: 2.2202759813938404, 32.0: 4.253931205661342, 33.0: 0.919831723511631, 35.0: 2.0805861145660156, 37.0: 0.7425346045369619, 39.0: 1.8007263667108249, 34.0: 2.490165246732843, 36.0: 0.6837865757399486, 38.0: 2.7431975748746638, 40.0: 2.560310196172903, 41.0: 2.480435748917053, 43.0: 1.403550106769017, 45.0: 3.2828972457373147, 47.0: 3.1311797727691033, 42.0: 1.270093073150128, 44.0: 4.916774471913408, 46.0: 4.99684018374227, 48.0: 1.8203402909867288, 69.0: 1.4806377782229534, 49.0: 2.7086716143465677, 51.0: 1.9121126973703055, 53.0: 4.63263352805131, 55.0: 1.0807183130436222, 50.0: 2.44741278778823, 52.0: 4.997874485051252, 54.0: 4.46378064880183, 56.0: 2.4983162788631303, 57.0: 1.3076329194187908, 58.0: 1.8380352775404618, 59.0: 1.4820335403170148, 60.0: 2.028073098005822, 61.0: 2.4908667882207247, 62.0: 4.974831508204851, 63.0: 4.410275732515502, 64.0: 3.9668068870141755, 65.0: 4.67672473515071, 66.0: 0.37874793078801483, 67.0: 3.9748554027293643, 68.0: 1.253744086349669, 1.0: 1.1638931346970438, 2.0: 4.212344207909008, 3.0: 4.794963173987856, 4.0: 0.816758633305737}}

    return settings_dict



def set_to_dict(mdl, pq=False):
    """
    Записывает уставки защит модели в словарь.

    Параметры:
        mdl  -- объект модели сети
        pq   -- если True, включает объекты ветви (p) и узла (q) в словарь (по умолчанию: False)

    Возвращает:
        dict -- {stat_id: {'I0_сраб': float, 't_сраб': float[, 'line': str, 'q': str, 'stage': int]}}
    """
    set_dict = {}
    for prot in mdl.bd:
        if pq: set_dict[prot.stat_id] = {'I0_сраб':prot.I0, 't_сраб':prot.t, 'line':prot.p.name, 'q':prot.q.name, 'stage':prot.stage}
        else: set_dict[prot.stat_id] = {'I0_сраб':prot.I0, 't_сраб':prot.t}
    return set_dict


def dict_to_set(mdl, set_dict, id_version = True):
    """
    Применяет уставки из словаря к модели.

    Поддерживает два формата словаря:
      id_version=True  -- {prot_id: {'I0_сраб': float, 't_сраб': float}}
      id_version=False -- {'I0_сраб': {prot_id: float}, 't_сраб': {prot_id: float}}

    Параметры:
        mdl        -- объект модели сети (изменяется на месте)
        set_dict   -- словарь уставок
        id_version -- формат словаря (по умолчанию: True)

    Возвращает:
        mdl -- модель с обновлёнными уставками
    """
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




def to_submdl(mdl, submdl_dict_row):
    """
    Создаёт и рассчитывает подмодель КЗ по строке словаря подрежимов.

    Добавляет промежуточный узел КЗ на линию, удаляет отключённые ветви,
    задаёт тип КЗ и выполняет расчёт токов.

    Параметры:
        mdl             -- базовая модель сети
        submdl_dict_row -- строка словаря {line_kz, percent, p_off, kz_type}

    Возвращает:
        submdl -- рассчитанная подмодель с узлом 'KZ'
    """
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


#@@@@@@@@@@@@@@@@@@@@@@@@@@_________КАЛЬКУЛЯТОР ПОДРЕЖИМОВ_________@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@@

def tokenize_expression(expression):
    """
    Разбивает DSL-выражение на токены с учётом вложенных скобок.

    Токены разделяются операторами '+' и '*' на верхнем уровне.
    Подвыражения в скобках сохраняются как единый токен.

    Параметры:
        expression -- строка DSL-выражения подрежимов

    Возвращает:
        list -- список строковых токенов
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
    """
    Разбивает DSL-выражение на группы слагаемых.

    Оператор '+' задаёт независимые наборы подрежимов (union),
    оператор '*' соединяет параметры внутри одного слагаемого (декартово произведение).

    Параметры:
        expression -- строка DSL-выражения

    Возвращает:
        list[list[str]] -- список групп, каждая группа — список токенов-множителей
    """
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
    """
    Разбирает один токен DSL в пару (функция, аргументы).

    Формат токена: ФУНКЦИЯ или ФУНКЦИЯ[арг1,арг2,...].
    Имя функции приводится к верхнему регистру.

    Параметры:
        item -- строковый токен

    Возвращает:
        tuple -- (func: str, args: list[str])
    """
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
    """
    Возвращает n линий с наибольшим током при КЗ на line_kz.

    Помещает КЗ в середину линии, рассчитывает токи во всех смежных ветвях
    и отбирает n ветвей с максимальным значением I0.

    Параметры:
        mdl      -- объект модели сети
        line_kz  -- имя линии с КЗ
        kz_types -- список типов КЗ (используется первый)
        n        -- количество линий для возврата

    Возвращает:
        tuple -- имена n линий с максимальным током (уникальные)
    """
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
    """
    Возвращает линии, индуктивно связанные с line_kz (DSL-функция ИНДУКЦ).

    Находит все ветви, смежные с line_kz через объекты взаимоиндукции mdl.bm.

    Параметры:
        mdl     -- объект модели сети
        line_kz -- имя линии с КЗ

    Возвращает:
        tuple -- имена смежных линий
    """
    p_off = ()
    line_obj = ktkz.p_search(mdl, p_name=line_kz)
    for m in mdl.bm:
        if m.p1==line_obj: p_off += (m.p2.name,)
        elif m.p2==line_obj: p_off += (m.p1.name,)
    return p_off
    
def belt(mdl, belt, line):
    """
    Возвращает линии пояса n вокруг line (DSL-функция ПОЯС[n]).

    Обходит топологию сети и возвращает ветви, находящиеся на расстоянии
    n ребёр от заданной линии (пояс защиты).

    Параметры:
        mdl   -- объект модели сети
        belt  -- номер пояса или список номеров (int или list[int])
        line  -- имя линии, от которой отсчитывается пояс

    Возвращает:
        tuple -- имена линий указанного пояса
    """
    line_obj = ktkz.p_search(mdl, p_name=line)
    p_off = ()
    if type(belt)!= list: belt = [belt]
    for b in belt:
        b = int(b)
        p_off += tuple(ktkz.belt_search(mdl=mdl, line=line_obj, n=b, return_names=True)[0][b])
    return p_off

def find_const_in_buscets(string, m, lines_kz, step, kz_types, mdl):
    """
    Извлекает константные параметры (ПЕРЕБОР, ЛИНИИКЗ, ШАГ, ТИПКЗ) из скобочного выражения.

    Обрабатывает только выражения без оператора '*' (не декартово произведение).

    Параметры:
        string   -- строка в скобках из DSL-выражения
        m        -- текущий параметр ПЕРЕБОР
        lines_kz -- текущий список линий КЗ
        step     -- текущий шаг перебора процентов
        kz_types -- текущие типы КЗ
        mdl      -- объект модели сети

    Возвращает:
        tuple -- (m, lines_kz, step, kz_types) с обновлёнными значениями
    """
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
    """
    Вычисляет подрежимы для суммарных наборов линий отключения в скобочном выражении.

    Обрабатывает DSL-функции ИНДУКЦ, ПОЯС, МАКСТОК, ОБЪЕКТЫ, записанные суммой в скобках.
    Пропускает выражения с '*' (передаёт управление submdl_calc_main).

    Параметры:
        string      -- строка в скобках из DSL-выражения
        m           -- параметр ПЕРЕБОР
        lines_kz    -- список линий КЗ
        step        -- шаг перебора процентов
        kz_types    -- типы КЗ
        mdl         -- объект модели сети
        submdl_dict -- накапливаемый словарь подрежимов
        log         -- вывод отладочной информации (по умолчанию: False)

    Возвращает:
        dict -- обновлённый submdl_dict
    """
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
    """
    Генерирует все подрежимы для одной линии КЗ и добавляет их в submdl_dict.

    Перебирает комбинации отключений (m ветвей из p_off), проценты вдоль линии
    (0%..100% с шагом step) и типы КЗ. Для каждой комбинации добавляет запись в словарь.

    Параметры:
        mdl         -- объект модели сети
        m           -- количество одновременно отключаемых линий (0 = нет отключений)
        line_kz     -- имя линии с КЗ
        step        -- шаг перебора позиции КЗ (доля от 0 до 1)
        p_off       -- кортеж имён линий-кандидатов для отключения
        kz_types    -- список типов КЗ ('A0', 'AB', 'ABC' и др.)
        submdl_dict -- накапливаемый словарь подрежимов
        log         -- вывод отладочной информации (по умолчанию: False)

    Возвращает:
        dict -- обновлённый submdl_dict
    """
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
    """
    Оркестратор парсинга DSL-строки подрежимов и генерации submdl_dict.

    Разбирает task_str по слагаемым (+) и множителям (*), извлекает параметры
    ПЕРЕБОР/ЛИНИИКЗ/ШАГ/ТИПКЗ и вызывает base_func для каждой комбинации.
    Рекурсивно обрабатывает вложенные скобочные выражения.

    Параметры:
        mdl         -- объект модели сети
        task_str    -- DSL-строка описания подрежимов
        submdl_dict -- накапливаемый словарь подрежимов (по умолчанию: {})
        m           -- начальное значение ПЕРЕБОР (по умолчанию: 0)
        lines_kz    -- начальный список линий КЗ (по умолчанию: [])
        step        -- начальный шаг (по умолчанию: 0)
        p_off       -- начальный набор отключений (по умолчанию: ())
        kz_types    -- начальный список типов КЗ (по умолчанию: [])
        log         -- вывод отладочной информации (по умолчанию: False)

    Возвращает:
        dict -- submdl_dict с добавленными подрежимами
    """
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