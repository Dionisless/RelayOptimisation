'''
kar_optimisation_pypeline.py - файл с финальными функциями для оптимизации параметров защит
'''

import kar_analyse as kanl
import kar_mrtkz as ktkz
import mrtkz3 as mrtkz
import optuna
import logging
from tqdm import tqdm

# Выводит защиты
def disable_prot(mdl):
    for d in mdl.bd:
        d.edit(I0=99999999,t=1000)
    return mdl

# Извлекаем данные для текущей подмодели 
def to_submdl(mdl, submdl_dict_row):  
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


# Рассчитывает ток первой ступени, отстраивая уставку от внешних токов кз с Котс
def calc_first_stage(mdl, submdl_dict, k_ots=1.1):
    # Перебираем все точки p в модели mdl
    for p in mdl.bp:
        Imax1 = 0  # Максимальное значение тока для первой защиты
        Imax2 = 0  # Максимальное значение тока для второй защиты

        # Перебираем все подрежимы из submdl_dict
        for sm_id in submdl_dict:
            sm = submdl_dict[sm_id]
            
            # Пропускаем, если точка p отключена в текущем подрежиме
            if p.name in sm['p_off']:
                continue

            # Создаем подмодель для текущего подрежима
            submdl = to_submdl(mdl, sm)
            #vis_I0_graph(submdl)
            # Проверяем, не является ли текущая линия линией КЗ
            if sm['line_kz'] != p.name:
                # Находим линию в подмодели
                line = ktkz.p_search(submdl, p_name=p.name)
                # Получаем ток I0 и угол ang
                try:
                    I0 = line.res1(['I0'], 'M')['I0']
                except:
                    vis_I0_graph(submdl)
                ang = line.res1(['I0'], '<f')['I0']

                # Определяем максимальное значение тока в зависимости от угла
                if (Imax1 < I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    Imax1 = I0  # Обновляем значение тока для первой защиты
                elif (Imax2 < I0) and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                    Imax2 = I0  # Обновляем значение тока для второй защиты

        # Настраиваем параметры для первой стадии первой защиты
        for d in p.q1_def:
            if d.stage == 1:
                if Imax1 <=100: Imax1 = 100
                d.edit(I0=Imax1 * k_ots, t=0)

        # Настраиваем параметры для первой стадии второй защиты
        for d in p.q2_def:
            if d.stage == 1:
                if Imax2<=100: Imax2 = 100
                d.edit(I0=Imax2 * k_ots, t=0)

    return mdl


# Проводит дополнительную отстройку первых ступеней от промежуточных подрежимов во время отключения линий
def first_stage_update(mdl, submdl_dict, kots=1.1):
    prot_work = kanl.analyze_relay_protections(mdl, submdl_dict)
    for work_id in prot_work:
        work = prot_work[work_id]
        if work['t']==0 and (not work['line'] in ['q1-kz','kz-q2',work['line_kz']]) and (work['id']>=0):
            #line = ktkz.p_search(mdl, p_name=work['line_kz'])
            #print(work)
            # находим защиты искомой линии
            line = ktkz.p_search(mdl, p_name=work['line'])     
            for d in line.q1_def:
                if d.stage==1: d1 = d
                else: d1 = 0
            for d in line.q2_def:
                if d.stage==1: d2 = d
                else: d1 = 0
      
            I0 = work['I0_line'][0]
            ang = work['I0_line'][1]
            # Определяем максимальное значение тока в зависимости от угла
            if d1!=0:
                if (d1.I0/kots < I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    #print(d1.I0, '<', I0)
                    d1.edit(I0=round(I0*kots,1), t=round(d1.t,1))  # Обновляем значение тока для первой защиты
            if d2!=0:
                if (d2.I0/kots < I0) and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                    #print(d2.I0, '<', I0)
                    d2.edit(I0=round(I0*kots,1), t=round(d2.t,1))  # Обновляем значение тока для второй защиты       
    return mdl


def calc_second_stage(mdl, submdl_dict, k_ch=0.9):
    """
    Функция для расчета второй ступени уставок релейной защиты.
    
    Аргументы:
    mdl -- объект модели с параметрами релейных защит.
    submdl_dict -- словарь подмоделей с параметрами для анализа срабатываний.
    k_ch -- коэффициент коррекции для минимального тока короткого замыкания (по умолчанию 0.9).
    
    Возвращает:
    mdl -- измененная модель с пересчитанными уставками для второй ступени защиты.
    """
    
    for p in mdl.bp:
        Imin_kz1 = float('inf')  # Инициализация переменной для хранения минимального тока КЗ первой очереди
        Imin_kz2 = float('inf')  # Инициализация переменной для хранения минимального тока КЗ второй очереди
        
        # Перебираем все подмодели в словаре submdl_dict
        for sm_id in submdl_dict:
            sm = submdl_dict[sm_id]
            
            # Пропускаем подмодели, где линия КЗ не совпадает с рассматриваемой защитой
            if sm['line_kz'] != p.name:
                continue
            
            # Преобразование подмодели для анализа
            submdl = to_submdl(mdl, sm)
            
            # Нахождение минимального тока КЗ для узла 1
            if p.q1 != 0:
                line = ktkz.p_search(submdl, p_name='q1-kz')  # Поиск линии для узла 1
                I0 = line.res1(['I0'], 'M')['I0']  # Значение тока КЗ
                ang = line.res1(['I0'], '<f')['I0']  # Угол фазы
                
                # Проверка на минимальный ток и соответствующий угол фазы
                if (Imin_kz1 > I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    Imin_kz1 = I0
            
            # Нахождение минимального тока КЗ для узла 2
            if p.q2 != 0:
                #vis_I0_graph(submdl)
                line = ktkz.p_search(submdl, p_name='kz-q2')  # Поиск линии для узла 2
                try: I0 = line.res2(['I0'], 'M')['I0']  # Значение тока КЗ
                except: vis_I0_graph(submdl)
                ang = line.res2(['I0'], '<f')['I0']  # Угол фазы
                
                # Проверка на минимальный ток и соответствующий угол фазы
                if (Imin_kz2 > I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    Imin_kz2 = I0
        
        # Устанавливаем уставки для второй ступени защиты для узла 1
        for d in p.q1_def:
            if d.stage == 2:
                d.edit(I0=round(Imin_kz1 * k_ch, 1), t=1.4)
        
        # Устанавливаем уставки для второй ступени защиты для узла 2
        for d in p.q2_def:
            if d.stage == 2:
                d.edit(I0=round(Imin_kz2 * k_ch, 1), t=1.4)
    
    return mdl


def second_stage_update(mdl, submdl_dict, k_ch=0.9):
    """
    This function updates the settings of the second stage of relay protections to ensure they detect faults (short circuits)
    on the line in all operating modes.
    
    Parameters:
    mdl - The model containing relay protection information.
    submdl_dict - Dictionary containing sub-model details.
    k_ch - Coefficient used to adjust the protection settings. Default is 0.9.
    
    Returns:
    Updated mdl with modified protection settings.
    """
    
    # Analyze relay protections based on the model and sub-model dictionary
    prot_work = kanl.analyze_relay_protections(mdl, submdl_dict)
    
    # Loop through each protection analysis result
    for work_id in prot_work:
        work = prot_work[work_id]
        
        # Check if the analysis result is indicating a fault scenario
        if work['id'] == -666:
            s_m = submdl_dict[work['submdl_id']]
            sm = {'id': s_m['id'],
                'line_kz': s_m['line_kz'],
                'kz_type': s_m['kz_type'],
                'percent': s_m['percent'],
                'p_off': tuple(set(s_m['p_off'] + work['p_off']))}
            submdl = to_submdl(mdl, sm)
            
            # Iterate over elements in the sub-model
            for p in submdl.bp:
                if p.name == 'q1-kz':
                    # Get current and angle of phase I0 from results
                    I0 = p.res1(['I0'], 'M')['I0']
                    ang = p.res1(['I0'], '<f')['I0']
                    
                    # Adjust protection settings based on current and angle values
                    for bp in mdl.bp:
                        if bp.name == sm['line_kz']:
                            for d in bp.q1_def:
                                if d.stage == 2 and I0 <= d.I0 / k_ch and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                                    d.edit(I0=I0 * k_ch, t=d.t)
                
                if p.name == 'kz-q2':
                    # Get current and angle of phase I0 from results for a different relay (q2)
                    I0 = p.res2(['I0'], 'M')['I0']
                    ang = p.res2(['I0'], '<f')['I0']
                    
                    # Adjust settings for q2 relay based on current and angle values
                    for bp in mdl.bp:
                        if bp.name == sm['line_kz']:
                            for d in bp.q2_def:
                                if d.stage == 2 and I0 <= d.I0 / k_ch and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                                    d.edit(I0=I0 * k_ch, t=d.t)
    
    return mdl



# Оптимизация времен 2 ступени с помощью optuna

def get_protection_stat_ids(mdl):
    protection_stat_ids = []
    for d in mdl.bd:
        if d.stage == 2:
            protection_stat_ids += [d.stat_id]
    return protection_stat_ids


def read_t_dict(mdl):
    t_dict = {}
    for d in mdl.bd:
        if d.stage == 2:
            t_dict[d.stat_id] = d.t
    return t_dict

def update_t(mdl, t_dict):
    for d in mdl.bd:
        if d.stage == 2:
            d.edit(I0=d.I0, t=(t_dict[d.stat_id]*0.2))

def objective(trial, mdl, submdl_dict, t_range, loss_params):
    # Определить пространство поиска для времени срабатывания каждой защиты
    t_dict = {}
    for stat_id in get_protection_stat_ids(mdl):
        t_dict[stat_id] = trial.suggest_int(f"t_{stat_id}", t_range[0], t_range[1])

    # Обновить модель новыми временами срабатывания
    update_t(mdl, t_dict)

    # Вычислить ошибку с учетом заданных весов
    loss = kanl.ML_func(mdl, submdl_dict, **loss_params)

    return loss

def optimize_protection_times(mdl, submdl_dict, n_trials=100, t_range=[1, 7], loss_params=None):
    if loss_params is None:
        loss_params = {
            'new_settings_dict': '',
            'range_prot_analyse': False,
            'show_result': False,
            'no_off': 10,
            'off': 0,
            'non_select': 1,
            'k_loss_time': 5,
            'k_loss_k_ch': 0,
            'no_off_dist': 5,
            'off_dist': 0,
            'non_select_dist': 0.3,
            'k_loss_time_dist': 0.2,
            'k_loss_k_ch_dist': 0,
        }
    else: loss_params = {
            'new_settings_dict': '',
            'range_prot_analyse': False,
            'show_result': False} | loss_params

    # Создать объект исследования и указать, что цель - минимизация
    study = optuna.create_study(direction="minimize")

    # Оптимизировать целевую функцию
    study.optimize(lambda trial: objective(trial, mdl, submdl_dict, t_range, loss_params), n_trials=n_trials)

    # Получить лучшие параметры
    best_params = study.best_params

    # Создать итоговый t_dict с лучшими параметрами
    best_t_dict = {int(k.split('_')[1]): v for k, v in best_params.items()}

    # Обновить модель лучшими параметрами
    update_t(mdl, best_t_dict)

    print(f"Лучшая ошибка: {study.best_value}")

    return best_t_dict

# поиск лучшей третьей ступени (по токам и временам между первыми двумя ступенями)
def get_protection_dict(mdl, two_stages=False):
    prot_dict = {}
    new_prot_dict_id = {}
    i = 0
    for p in mdl.bp:
        if p.q1 != 0:
            prot_dict[i] = {'I0': [], 't': []}
            if two_stages:  new_prot_dict_id[i] = {3: '', 4: ''}
            for d in p.q1_def:
                if d.stage in [1, 2]:
                    prot_dict[i]['I0'].append(d.I0)
                    prot_dict[i]['t'].append(d.t)
                if two_stages:
                    if d.stage==3:
                        new_prot_dict_id[i][3] = d
                    elif d.stage==4:
                        new_prot_dict_id[i][4] = d
                else:
                    if d.stage==3:
                        new_prot_dict_id[i] = d   
                    
            i += 1
        if p.q2 != 0:
            prot_dict[i] = {'I0': [], 't': []}
            if two_stages:  new_prot_dict_id[i] = {3: '', 4: ''}
            for d in p.q2_def:
                if d.stage in [1, 2]:
                    prot_dict[i]['I0'].append(d.I0)
                    prot_dict[i]['t'].append(d.t)

                if two_stages:
                    if d.stage==3:
                        new_prot_dict_id[i][3] = d
                    elif d.stage==4:
                        new_prot_dict_id[i][4] = d
                else:
                    if d.stage==3:
                        new_prot_dict_id[i] = d                    
            i += 1
    #print(prot_dict)
    #print(new_prot_dict_id)
    return prot_dict, new_prot_dict_id






def objective_third(trial, mdl, submdl_dict, prot_dict, new_prot_dict_id, two_stages, loss_params, loss_callback=None):
    if loss_params is None:
        loss_params = {
            'new_settings_dict': '',
            'range_prot_analyse': False,
            'show_result': False,
            'no_off': 10,
            'off': 0,
            'non_select': 1,
            'k_loss_time': 5,
            'k_loss_k_ch': 0,
            'no_off_dist': 5,
            'off_dist': 0,
            'non_select_dist': 0.3,
            'k_loss_time_dist': 0.2,
            'k_loss_k_ch_dist': 0,
        }
    else: 
        loss_params = {
            'new_settings_dict': '',
            'range_prot_analyse': False,
            'show_result': False
        } | loss_params
        
    # Оптимизируем параметры третьей ступени
    for i, prot in prot_dict.items():
        I0_min, I0_max = min(prot['I0']), max(prot['I0'])
        t_min, t_max = min(prot['t']), max(prot['t'])

        # Предлагаем значения для третьей ступени
        I0_3 = round(trial.suggest_float(f"I0_3_{i}", I0_min, I0_max), 1)
        # Предлагаем дискретные значения времени с шагом 0.2
        t_steps = int((t_max - t_min) / 0.2) + 1
        t_3_step = trial.suggest_int(f"t_3_step_{i}", 0, t_steps - 1)
        t_3 = round(t_min + t_3_step * 0.2, 1)

        if two_stages:
            # Предлагаем значения для четвертой ступени
            I0_4 = round(trial.suggest_float(f"I0_4_{i}", I0_min, I0_max), 1)
            t_4_step = trial.suggest_int(f"t_4_step_{i}", 0, t_steps - 1)
            t_4 = round(t_min + t_4_step * 0.2, 1)

            # Обновляем третью ступень в модели
            new_prot_dict_id[i][3].edit(I0=I0_3, t=t_3)
            # Обновляем четвертую ступень в модели
            new_prot_dict_id[i][4].edit(I0=I0_4, t=t_4)

        else:
            # Обновляем третью ступень в модели
            new_prot_dict_id[i].edit(I0=I0_3, t=t_3)

    # Вычисляем ошибку с учетом заданных весов
    loss = kanl.ML_func(mdl, submdl_dict, **loss_params)
    
    # Вызываем loss_callback с текущим значением ошибки
    if loss_callback is not None:
        loss_callback(loss)
        
    return loss

def optimize_third_stage_settings(mdl, submdl_dict, n_trials=100, two_stages=False, loss_params=None, loss_callback=None):
    prot_dict, new_prot_dict_id = get_protection_dict(mdl, two_stages)

    study = optuna.create_study(direction="minimize")
    study.optimize(
        lambda trial: objective_third(trial, mdl, submdl_dict, prot_dict, new_prot_dict_id, two_stages, loss_params, loss_callback),
        n_trials=n_trials,
    )

    best_params = study.best_params
    print(f"Best loss: {study.best_value}")

    # Применяем лучшие параметры к модели
    for i in range(len(prot_dict)):
        if two_stages:
            I0_3 = best_params[f"I0_3_{i}"]
            t_3_step = best_params[f"t_3_step_{i}"]
            t_min, t_max = min(prot_dict[i]['t']), max(prot_dict[i]['t'])
            t_3 = t_min + t_3_step * 0.2
            new_prot_dict_id[i][3].edit(I0=round(I0_3,1), t=round(t_3, 1))

            I0_4 = best_params[f"I0_4_{i}"]
            t_4_step = best_params[f"t_4_step_{i}"]
            t_4 = t_min + t_4_step * 0.2
            new_prot_dict_id[i][4].edit(I0=round(I0_4, 1), t=round(t_4, 1))    
        else:
            I0_3 = best_params[f"I0_3_{i}"]
            t_3_step = best_params[f"t_3_step_{i}"]
            t_min, t_max = min(prot_dict[i]['t']), max(prot_dict[i]['t'])
            t_3 = t_min + t_3_step * 0.2
            new_prot_dict_id[i].edit(I0=round(I0_3, 1), t=round(t_3, 1))
                
    return best_params, mdl

# версия без динамически обновляющегося графика
'''
def objective_third(trial, mdl, submdl_dict, prot_dict, new_prot_dict_id, two_stages, loss_params):
    if loss_params is None:
        loss_params = {
            'new_settings_dict': '',
            'range_prot_analyse': False,
            'show_result': False,
            'no_off': 10,
            'off': 0,
            'non_select': 1,
            'k_loss_time': 5,
            'k_loss_k_ch': 0,
            'no_off_dist': 5,
            'off_dist': 0,
            'non_select_dist': 0.3,
            'k_loss_time_dist': 0.2,
            'k_loss_k_ch_dist': 0,
        }
    else: loss_params = {
            'new_settings_dict': '',
            'range_prot_analyse': False,
            'show_result': False} | loss_params    
    # Оптимизировать параметры третьей ступени
    for i, prot in prot_dict.items():
        I0_min, I0_max = min(prot['I0']), max(prot['I0'])
        t_min, t_max = min(prot['t']), max(prot['t'])

        # Предложить значения для третьей ступени
        I0_3 = trial.suggest_float(f"I0_3_{i}", I0_min, I0_max)
        # Предложить дискретные значения времени с шагом 0.2
        t_steps = int((t_max - t_min) / 0.2) + 1
        t_3_step = trial.suggest_int(f"t_3_step_{i}", 0, t_steps - 1)
        t_3 = t_min + t_3_step * 0.2

        if two_stages:
            # Предложить значения для четвертой ступени
            I0_4 = trial.suggest_float(f"I0_4_{i}", I0_min, I0_max)
            t_4_step = trial.suggest_int(f"t_4_step_{i}", 0, t_steps - 1)
            t_4 = t_min + t_4_step * 0.2

            # Добавить третью ступень в модель
            new_prot_dict_id[i][3].edit(I0=I0_3, t=t_3)
            # Добавить четвертую ступень в модель
            new_prot_dict_id[i][4].edit(I0=I0_4, t=t_4)

        else:
            # Добавить третью ступень в модель
            new_prot_dict_id[i].edit(I0=I0_3, t=t_3)

    # Вычислить ошибку с учетом заданных весов
    loss = kanl.ML_func(mdl, submdl_dict, **loss_params)

    return loss

def optimize_third_stage_settings(mdl, submdl_dict, n_trials=100, two_stages=False, loss_params=None):
    prot_dict, new_prot_dict_id = get_protection_dict(mdl, two_stages)

    # Создаем индикатор прогресса с использованием tqdm
    #pbar = tqdm(total=n_trials, desc="Оптимизация третьей ступени")

    # Callback функция для обновления прогресса
    #def tqdm_callback(study, trial):
    #    pbar.update(1)

    study = optuna.create_study(direction="minimize")
    study.optimize(lambda trial: objective_third(trial, mdl, submdl_dict, prot_dict, new_prot_dict_id, two_stages, loss_params), n_trials=n_trials) #,callbacks=[tqdm_callback])

    #pbar.close()

    best_params = study.best_params
    print(f"Best loss: {study.best_value}")

    # Apply the best parameters to the model
    for i in range(len(prot_dict)):
        if two_stages:
            I0_3 = best_params[f"I0_3_{i}"]
            t_3_step = best_params[f"t_3_step_{i}"]
            t_min, t_max = min(prot_dict[i]['t']), max(prot_dict[i]['t'])
            t_3 = t_min + t_3_step * 0.2
            new_prot_dict_id[i][3].edit(I0=I0_3, t=t_3)

            I0_4 = best_params[f"I0_4_{i}"]
            t_4_step = best_params[f"t_4_step_{i}"]
            t_4 = t_min + t_4_step * 0.2
            new_prot_dict_id[i][4].edit(I0=I0_4, t=t_4)    
            
        else:
            I0_3 = best_params[f"I0_3_{i}"]
            t_3_step = best_params[f"t_3_step_{i}"]
            t_min, t_max = min(prot_dict[i]['t']), max(prot_dict[i]['t'])
            t_3 = t_min + t_3_step * 0.2
            new_prot_dict_id[i].edit(I0=I0_3, t=t_3)
            
    return best_params, mdl
'''

'''

def main_pypeline(extended_log=True):
    if extended_log: show_iterations= n_iterations + 9
    else:            show_iterations= n_iterations + 4
        
    self.log_queue.put(f'Начата оптимизация {n_stages} ступеней защит сети. 
    \nКоличество итераций целевой функции {n_iterations+} с расчетным временем выполнения {calculation_time}')
	mdl = disable_prot(mdl)
	if extended_log==True: 
        self.log_queue.put('\nВыводим все защиты (disable_prot)')
    
    submdl = calc_first_stage(mdl, submdl_dict, k_ots)
	if extended_log==True:
        self.log_queue.put('\nОтстраиваем первую ступениь во всех подрежимах (calc_first_stage)')
        result = kanl.ML_func(submdl,submdl_dict,extended_result=True)
        self.log_queue.put(f'Общая ошибка: {result['loss']}\nКоличество неселективных срабатываний: {result['non_select_count']}\nКоличество селективных срабатываний: {result['select_count']}\nДоля селективных срабатываний:{result['select_share']}%\nКоличество неотключений: {result['no_off_count']}\nСреднее время отключения: {['mean_time']}')

    submdl = first_stage_update(submdl, submdl_dict, k_ots)
	if extended_log==True:
        self.log_queue.put('\nАнализируем срабатывания, отстраиваем первую ступень в упущенных подрежимах (first_stage_update)')
        result = kanl.ML_func(submdl,submdl_dict,extended_result=True)
        self.log_queue.put(f'Общая ошибка: {result['loss']}\nКоличество неселективных срабатываний: {result['non_select_count']}\nКоличество селективных срабатываний: {result['select_count']}\nДоля селективных срабатываний:{result['select_share']}%\nКоличество неотключений: {result['no_off_count']}\nСреднее время отключения: {['mean_time']}')

    submdl = calc_second_stage(submdl , submdl_dict, k_ch)
    if extended_log==True:
        self.log_queue.put('\nВыводим вторую ступень на чувствование тока КЗ на линии во всех подрежимах (calc_second_stage)')
        result = kanl.ML_func(submdl,submdl_dict,extended_result=True)
        self.log_queue.put(f'Общая ошибка: {result['loss']}\nКоличество неселективных срабатываний: {result['non_select_count']}\nКоличество селективных срабатываний: {result['select_count']}\nДоля селективных срабатываний:{result['select_share']}%\nКоличество неотключений: {result['no_off_count']}\nСреднее время отключения: {['mean_time']}')

    submdl = second_stage_update(submdl, submdl_dict, k_ch)
    if extended_log==True:
        self.log_queue.put('\nВыводим вторую ступень на чувствование тока КЗ в упущенных подрежимах (update_second_stage)')
        result = kanl.ML_func(submdl,submdl_dict,extended_result=True)
        self.log_queue.put(f'Общая ошибка: {result['loss']}\nКоличество неселективных срабатываний: {result['non_select_count']}\nКоличество селективных срабатываний: {result['select_count']}\nДоля селективных срабатываний:{result['select_share']}%\nКоличество неотключений: {result['no_off_count']}\nСреднее время отключения: {['mean_time']}')
        
    if n_stages==2:
        optuna.logging.set_verbosity(optuna.logging.WARNING)
        optimize_protection_times(submdl, submdl_dict, n_trials=n_iterations, t_range=[1,7], loss_params=loss_params)
        self.log_queue.put('\nОптимизируем времена срабатывания второй ступени (optimized_second_protection_times)')
        result = kanl.ML_func(submdl,submdl_dict,extended_result=True)
        self.log_queue.put(f'Общая ошибка: {result['loss']}\nКоличество неселективных срабатываний: {result['non_select_count']}\nКоличество селективных срабатываний: {result['select_count']}\nДоля селективных срабатываний:{result['select_share']}%\nКоличество неотключений: {result['no_off_count']}\nСреднее время отключения: {['mean_time']}')
        
    elif n_stages in [3, 4]:
        if n_stages==3: 
            two_stages=False
            self.log_queue.put('\nВводим третью ступень с параметрами между первой и второй и оптимизируем ее параметры (optimize_third_stage_settings)')
        else: 
            two_stages=True
            self.log_queue.put('\nВводим третью и четвертую ступень с параметрами между первой и второй и оптимизируем ее параметры (optimize_third_stage_settings)')

        best_sett, submdl = optimize_third_stage_settings(submdl, submdl_dict, n_trials=n_iterations, two_stages=two_stages, loss_params=loss_params)
        result = kanl.ML_func(submdl,submdl_dict,extended_result=True)
        self.log_queue.put(f'Общая ошибка: {result['loss']}\nКоличество неселективных срабатываний: {result['non_select_count']}\nКоличество селективных срабатываний: {result['select_count']}\nДоля селективных срабатываний:{result['select_share']}%\nКоличество неотключений: {result['no_off_count']}\nСреднее время отключения: {['mean_time']}')
        # После оптимизации
        best_loss = result['loss']
        self.log_queue.put(f"Оптимизация завершена. Лучшая ошибка: {best_loss}")

        except Exception as e:
            self.log_queue.put(f"Ошибка во время оптимизации: {str(e)}")
        finally:
            # Восстановление stdout
            sys.stdout = old_stdout
            log_output = mystdout.getvalue()
            self.log_queue.put(log_output)
'''