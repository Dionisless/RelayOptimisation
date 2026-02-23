'''
kar_optimisation_pypeline.py — функции для расчёта и оптимизации параметров релейной защиты.

Пайплайн оптимизации выполняется в несколько этапов:
  1. disable_prot    — вывод всех защит в нерабочее состояние
  2. calc_first_stage + first_stage_update  — расчёт и корректировка 1 ступени
  3. calc_second_stage + second_stage_update — расчёт и корректировка 2 ступени
  4. optimize_protection_times              — оптимизация времён 2 ступени (Optuna)
     ИЛИ optimize_third_stage_settings     — оптимизация 3/4 ступеней (Optuna)
'''

import kar_analyse as kanl
import kar_mrtkz as ktkz
import mrtkz3 as mrtkz
import optuna
import logging
from tqdm import tqdm


def disable_prot(mdl):
    """
    Выводит все защиты модели в условно-нерабочее состояние.

    Устанавливает уставку тока I0=99999999 А и время срабатывания t=1000 с
    для каждой защиты в модели. Используется как начальный шаг пайплайна,
    чтобы сбросить все предыдущие настройки перед расчётом новых уставок.

    Параметры:
        mdl -- объект модели mrtkz.Model с перечнем защит в mdl.bd

    Возвращает:
        mdl -- та же модель с обнулёнными защитами
    """
    for d in mdl.bd:
        d.edit(I0=99999999, t=1000)
    return mdl


def to_submdl(mdl, submdl_dict_row):
    """
    Создаёт подмодель для заданного сценария короткого замыкания (КЗ).

    По строке submdl_dict_row добавляет промежуточный узел КЗ на линию
    в указанном проценте, отключает заданные линии (p_off) и выполняет
    расчёт токов КЗ заданного типа.

    Параметры:
        mdl            -- базовая модель mrtkz.Model
        submdl_dict_row -- словарь с параметрами подрежима:
                           {'line_kz': str, 'percent': float,
                            'p_off': tuple, 'kz_type': str}

    Возвращает:
        submdl -- рассчитанная подмодель с узлом КЗ в конце bq
    """
    line = submdl_dict_row['line_kz']
    percent = submdl_dict_row['percent']
    p_off = submdl_dict_row['p_off']
    kz_type = submdl_dict_row['kz_type']

    line_obj = ktkz.p_search(mdl, p_name=line)

    submdl = ktkz.kz_q(mdl, line=line_obj, percentage_of_line=percent,
                        show_G=False, show_par=False, kaskade=False)

    submdl = ktkz.p_del(submdl, del_p_name=p_off,
                         show_G=False, show_par=False, node=False)

    mrtkz.N(submdl, 'KZ', submdl.bq[-1], kz_type)

    submdl.Calc()
    return submdl


def calc_first_stage(mdl, submdl_dict, k_ots=1.1):
    """
    Рассчитывает уставки тока первой ступени защиты для всех линий.

    Для каждой линии перебирает все подрежимы из submdl_dict,
    находит максимальный ток КЗ на внешних относительно данной линии
    участках (ток, протекающий через эту линию при внешних КЗ).
    Уставка первой ступени устанавливается с коэффициентом отстройки k_ots,
    что гарантирует несрабатывание при внешних КЗ. Время срабатывания = 0 с.

    Параметры:
        mdl         -- модель mrtkz.Model с защитами в mdl.bp
        submdl_dict -- словарь подрежимов {id: {'line_kz', 'percent', 'p_off', 'kz_type'}}
        k_ots       -- коэффициент отстройки (по умолчанию: 1.1)

    Возвращает:
        mdl -- модель с обновлёнными уставками первой ступени (stage==1)
    """
    for p in mdl.bp:
        Imax1 = 0  # максимальный ток для защиты со стороны узла q1
        Imax2 = 0  # максимальный ток для защиты со стороны узла q2

        for sm_id in submdl_dict:
            sm = submdl_dict[sm_id]

            if p.name in sm['p_off']:
                continue

            submdl = to_submdl(mdl, sm)

            # перебираем только внешние КЗ (не на самой линии p)
            if sm['line_kz'] != p.name:
                line = ktkz.p_search(submdl, p_name=p.name)
                try:
                    I0 = line.res1(['I0'], 'M')['I0']
                except:
                    ktkz.print_G(submdl, I=True)
                ang = line.res1(['I0'], '<f')['I0']

                # угол определяет направление тока: q1→q2 или q2→q1
                if (Imax1 < I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    Imax1 = I0
                elif (Imax2 < I0) and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                    Imax2 = I0

        for d in p.q1_def:
            if d.stage == 1:
                if Imax1 <= 100:
                    Imax1 = 100
                d.edit(I0=Imax1 * k_ots, t=0)

        for d in p.q2_def:
            if d.stage == 1:
                if Imax2 <= 100:
                    Imax2 = 100
                d.edit(I0=Imax2 * k_ots, t=0)

    return mdl


def first_stage_update(mdl, submdl_dict, kots=1.1):
    """
    Корректирует уставки первой ступени для переходных режимов (отключения линий).

    После calc_first_stage возможны ложные срабатывания первой ступени (t=0)
    при переходных режимах, когда часть линий уже отключена. Функция выявляет
    такие случаи, анализируя результаты analyze_relay_protections, и повышает
    уставку тока первой ступени на проблемных линиях.

    Параметры:
        mdl         -- модель с уставками после calc_first_stage
        submdl_dict -- словарь подрежимов
        kots        -- коэффициент отстройки (по умолчанию: 1.1)

    Возвращает:
        mdl -- модель с откорректированными уставками первой ступени
    """
    prot_work = kanl.analyze_relay_protections(mdl, submdl_dict)
    for work_id in prot_work:
        work = prot_work[work_id]
        # ищем ложные срабатывания 1 ступени на линиях, не являющихся линией КЗ
        if work['t'] == 0 and (not work['line'] in ['q1-kz', 'kz-q2', work['line_kz']]) and (work['id'] >= 0):
            line = ktkz.p_search(mdl, p_name=work['line'])
            for d in line.q1_def:
                if d.stage == 1:
                    d1 = d
                else:
                    d1 = 0
            for d in line.q2_def:
                if d.stage == 1:
                    d2 = d
                else:
                    d1 = 0

            I0 = work['I0_line'][0]
            ang = work['I0_line'][1]

            if d1 != 0:
                if (d1.I0 / kots < I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    d1.edit(I0=round(I0 * kots, 1), t=round(d1.t, 1))
            if d2 != 0:
                if (d2.I0 / kots < I0) and ((-20 <= ang <= 160) or (340 <= ang <= 360)):
                    d2.edit(I0=round(I0 * kots, 1), t=round(d2.t, 1))
    return mdl


def calc_second_stage(mdl, submdl_dict, k_ch=0.9):
    """
    Рассчитывает уставки тока второй ступени защиты для всех линий.

    Для каждой линии находит минимальный ток КЗ при КЗ непосредственно
    на этой линии (сценарии, где line_kz == p.name). Уставка второй ступени
    устанавливается как k_ch × Imin_кз, что гарантирует надёжное чувствование
    КЗ на собственной линии. Время срабатывания = 1.4 с.

    Параметры:
        mdl         -- модель mrtkz.Model
        submdl_dict -- словарь подрежимов
        k_ch        -- коэффициент чувствительности (по умолчанию: 0.9)

    Возвращает:
        mdl -- модель с обновлёнными уставками второй ступени (stage==2)
    """
    for p in mdl.bp:
        Imin_kz1 = float('inf')
        Imin_kz2 = float('inf')

        for sm_id in submdl_dict:
            sm = submdl_dict[sm_id]

            if sm['line_kz'] != p.name:
                continue

            submdl = to_submdl(mdl, sm)

            if p.q1 != 0:
                line = ktkz.p_search(submdl, p_name='q1-kz')
                I0 = line.res1(['I0'], 'M')['I0']
                ang = line.res1(['I0'], '<f')['I0']
                if (Imin_kz1 > I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    Imin_kz1 = I0

            if p.q2 != 0:
                line = ktkz.p_search(submdl, p_name='kz-q2')
                try:
                    I0 = line.res2(['I0'], 'M')['I0']
                except:
                    ktkz.print_G(submdl, I=True)
                ang = line.res2(['I0'], '<f')['I0']
                if (Imin_kz2 > I0) and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                    Imin_kz2 = I0

        for d in p.q1_def:
            if d.stage == 2:
                d.edit(I0=round(Imin_kz1 * k_ch, 1), t=1.4)

        for d in p.q2_def:
            if d.stage == 2:
                d.edit(I0=round(Imin_kz2 * k_ch, 1), t=1.4)

    return mdl


def second_stage_update(mdl, submdl_dict, k_ch=0.9):
    """
    Корректирует уставки второй ступени для подрежимов с неотключением КЗ.

    После calc_second_stage возможны подрежимы (id=-666: ни одна защита
    не сработала). Функция находит такие подрежимы, создаёт расширенную
    подмодель с дополнительными отключёнными линиями и понижает уставку
    второй ступени, чтобы обеспечить чувствование тока КЗ.

    Параметры:
        mdl         -- модель с уставками после calc_second_stage
        submdl_dict -- словарь подрежимов
        k_ch        -- коэффициент чувствительности (по умолчанию: 0.9)

    Возвращает:
        mdl -- модель с откорректированными уставками второй ступени
    """
    prot_work = kanl.analyze_relay_protections(mdl, submdl_dict)

    for work_id in prot_work:
        work = prot_work[work_id]

        if work['id'] == -666:
            s_m = submdl_dict[work['submdl_id']]
            sm = {'id': s_m['id'],
                  'line_kz': s_m['line_kz'],
                  'kz_type': s_m['kz_type'],
                  'percent': s_m['percent'],
                  'p_off': tuple(set(s_m['p_off'] + work['p_off']))}
            submdl = to_submdl(mdl, sm)

            for p in submdl.bp:
                if p.name == 'q1-kz':
                    I0 = p.res1(['I0'], 'M')['I0']
                    ang = p.res1(['I0'], '<f')['I0']
                    for bp in mdl.bp:
                        if bp.name == sm['line_kz']:
                            for d in bp.q1_def:
                                if d.stage == 2 and I0 <= d.I0 / k_ch and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                                    d.edit(I0=I0 * k_ch, t=d.t)

                if p.name == 'kz-q2':
                    I0 = p.res2(['I0'], 'M')['I0']
                    ang = p.res2(['I0'], '<f')['I0']
                    for bp in mdl.bp:
                        if bp.name == sm['line_kz']:
                            for d in bp.q2_def:
                                if d.stage == 2 and I0 <= d.I0 / k_ch and ((-200 <= ang <= -20) or (160 <= ang <= 340)):
                                    d.edit(I0=I0 * k_ch, t=d.t)

    return mdl


def get_protection_stat_ids(mdl):
    """
    Возвращает список stat_id всех защит второй ступени в модели.

    Параметры:
        mdl -- модель mrtkz.Model

    Возвращает:
        list -- список stat_id защит с stage==2
    """
    protection_stat_ids = []
    for d in mdl.bd:
        if d.stage == 2:
            protection_stat_ids += [d.stat_id]
    return protection_stat_ids


def read_t_dict(mdl):
    """
    Считывает текущие времена срабатывания всех защит второй ступени.

    Параметры:
        mdl -- модель mrtkz.Model

    Возвращает:
        dict -- словарь {stat_id: t} для защит с stage==2
    """
    t_dict = {}
    for d in mdl.bd:
        if d.stage == 2:
            t_dict[d.stat_id] = d.t
    return t_dict


def update_t(mdl, t_dict):
    """
    Обновляет времена срабатывания защит второй ступени по словарю t_dict.

    Значения из t_dict умножаются на 0.2 для перевода из дискретных шагов
    в секунды.

    Параметры:
        mdl    -- модель mrtkz.Model
        t_dict -- словарь {stat_id: int_шаг} с новыми временами
    """
    for d in mdl.bd:
        if d.stage == 2:
            d.edit(I0=d.I0, t=(t_dict[d.stat_id] * 0.2))


def objective(trial, mdl, submdl_dict, t_range, loss_params):
    """
    Целевая функция Optuna для оптимизации времён срабатывания второй ступени.

    Для каждой защиты второй ступени предлагает целочисленный шаг времени
    в диапазоне t_range, обновляет модель и вычисляет функцию потерь ML_func.

    Параметры:
        trial       -- объект Optuna Trial
        mdl         -- модель mrtkz.Model
        submdl_dict -- словарь подрежимов
        t_range     -- список [t_min_шаг, t_max_шаг]
        loss_params -- параметры функции потерь ML_func

    Возвращает:
        float -- значение функции потерь для данного набора параметров
    """
    t_dict = {}
    for stat_id in get_protection_stat_ids(mdl):
        t_dict[stat_id] = trial.suggest_int(f"t_{stat_id}", t_range[0], t_range[1])

    update_t(mdl, t_dict)

    loss = kanl.ML_func(mdl, submdl_dict, **loss_params)

    return loss


def optimize_protection_times(mdl, submdl_dict, n_trials=100, t_range=[1, 7], loss_params=None):
    """
    Оптимизирует времена срабатывания второй ступени защит с помощью Optuna.

    Минимизирует функцию потерь ML_func, перебирая различные комбинации
    времён срабатывания для всех защит второй ступени. Обновляет модель
    найденными оптимальными параметрами.

    Параметры:
        mdl         -- модель mrtkz.Model
        submdl_dict -- словарь подрежимов
        n_trials    -- количество итераций оптимизации (по умолчанию: 100)
        t_range     -- диапазон дискретных шагов времени [min, max]
                       (шаг = 0.2 с, по умолчанию: [1, 7] → [0.2 с, 1.4 с])
        loss_params -- словарь весовых коэффициентов для ML_func;
                       если None, используются значения по умолчанию

    Возвращает:
        dict -- словарь лучших параметров {stat_id: шаг_времени}
    """
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
            'show_result': False} | loss_params

    study = optuna.create_study(direction="minimize")
    study.optimize(
        lambda trial: objective(trial, mdl, submdl_dict, t_range, loss_params),
        n_trials=n_trials
    )

    best_params = study.best_params
    best_t_dict = {int(k.split('_')[1]): v for k, v in best_params.items()}
    update_t(mdl, best_t_dict)

    print(f"Лучшая ошибка: {study.best_value}")

    return best_t_dict


def get_protection_dict(mdl, two_stages=False):
    """
    Собирает словари уставок и объектов защит для оптимизации 3/4 ступеней.

    Формирует два словаря:
    - prot_dict: диапазоны [I0_min, I0_max] и [t_min, t_max] существующих
      1-й и 2-й ступеней — задают пространство поиска для 3-й/4-й ступеней
    - new_prot_dict_id: ссылки на объекты защит 3-й (и 4-й при two_stages)
      ступеней для последующего обновления

    Параметры:
        mdl        -- модель mrtkz.Model
        two_stages -- если True, ищет и возвращает объекты 3-й И 4-й ступеней
                      (по умолчанию: False — только 3-я ступень)

    Возвращает:
        prot_dict        -- dict {i: {'I0': [I0_st1, I0_st2], 't': [t_st1, t_st2]}}
        new_prot_dict_id -- dict {i: объект_защиты_3} или {i: {3: объект, 4: объект}}
    """
    prot_dict = {}
    new_prot_dict_id = {}
    i = 0
    for p in mdl.bp:
        if p.q1 != 0:
            prot_dict[i] = {'I0': [], 't': []}
            if two_stages:
                new_prot_dict_id[i] = {3: '', 4: ''}
            for d in p.q1_def:
                if d.stage in [1, 2]:
                    prot_dict[i]['I0'].append(d.I0)
                    prot_dict[i]['t'].append(d.t)
                if two_stages:
                    if d.stage == 3:
                        new_prot_dict_id[i][3] = d
                    elif d.stage == 4:
                        new_prot_dict_id[i][4] = d
                else:
                    if d.stage == 3:
                        new_prot_dict_id[i] = d
            i += 1
        if p.q2 != 0:
            prot_dict[i] = {'I0': [], 't': []}
            if two_stages:
                new_prot_dict_id[i] = {3: '', 4: ''}
            for d in p.q2_def:
                if d.stage in [1, 2]:
                    prot_dict[i]['I0'].append(d.I0)
                    prot_dict[i]['t'].append(d.t)
                if two_stages:
                    if d.stage == 3:
                        new_prot_dict_id[i][3] = d
                    elif d.stage == 4:
                        new_prot_dict_id[i][4] = d
                else:
                    if d.stage == 3:
                        new_prot_dict_id[i] = d
            i += 1
    return prot_dict, new_prot_dict_id


def objective_third(trial, mdl, submdl_dict, prot_dict, new_prot_dict_id, two_stages, loss_params, loss_callback=None):
    """
    Целевая функция Optuna для оптимизации 3-й (и 4-й) ступеней защит.

    Для каждой защиты предлагает значения I0 и дискретный шаг времени t
    в диапазоне, ограниченном уставками 1-й и 2-й ступеней. При two_stages=True
    оптимизирует параметры 3-й и 4-й ступеней одновременно. После обновления
    модели вычисляет ML_func и опционально вызывает loss_callback для
    отображения прогресса в GUI.

    Параметры:
        trial           -- объект Optuna Trial
        mdl             -- модель mrtkz.Model
        submdl_dict     -- словарь подрежимов
        prot_dict       -- диапазоны I0 и t из get_protection_dict
        new_prot_dict_id -- ссылки на объекты защит 3/4 ступеней
        two_stages      -- если True, оптимизирует 3-ю и 4-ю ступени
        loss_params     -- параметры функции потерь ML_func
        loss_callback   -- функция обратного вызова (loss) → None для GUI (по умолчанию: None)

    Возвращает:
        float -- значение функции потерь
    """
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

    for i, prot in prot_dict.items():
        I0_min, I0_max = min(prot['I0']), max(prot['I0'])
        t_min, t_max = min(prot['t']), max(prot['t'])

        I0_3 = round(trial.suggest_float(f"I0_3_{i}", I0_min, I0_max), 1)
        # дискретный шаг 0.2 с для времени срабатывания
        t_steps = int((t_max - t_min) / 0.2) + 1
        t_3_step = trial.suggest_int(f"t_3_step_{i}", 0, t_steps - 1)
        t_3 = round(t_min + t_3_step * 0.2, 1)

        if two_stages:
            I0_4 = round(trial.suggest_float(f"I0_4_{i}", I0_min, I0_max), 1)
            t_4_step = trial.suggest_int(f"t_4_step_{i}", 0, t_steps - 1)
            t_4 = round(t_min + t_4_step * 0.2, 1)
            new_prot_dict_id[i][3].edit(I0=I0_3, t=t_3)
            new_prot_dict_id[i][4].edit(I0=I0_4, t=t_4)
        else:
            new_prot_dict_id[i].edit(I0=I0_3, t=t_3)

    loss = kanl.ML_func(mdl, submdl_dict, **loss_params)

    if loss_callback is not None:
        loss_callback(loss)

    return loss


def optimize_third_stage_settings(mdl, submdl_dict, n_trials=100, two_stages=False, loss_params=None, loss_callback=None):
    """
    Оптимизирует уставки 3-й (и 4-й) ступеней защит с помощью Optuna.

    Пространство поиска для каждой защиты ограничено диапазоном уставок
    1-й и 2-й ступеней (I0 и t). Минимизирует функцию потерь ML_func.
    По окончании применяет найденные оптимальные параметры к модели.

    Параметры:
        mdl           -- модель mrtkz.Model
        submdl_dict   -- словарь подрежимов
        n_trials      -- количество итераций оптимизации (по умолчанию: 100)
        two_stages    -- если True, оптимизирует 3-ю и 4-ю ступени совместно
                         (по умолчанию: False — только 3-я ступень)
        loss_params   -- параметры ML_func; если None, используются значения
                         по умолчанию
        loss_callback -- функция обратного вызова для GUI (по умолчанию: None)

    Возвращает:
        best_params -- dict с лучшими найденными параметрами (Optuna)
        mdl         -- модель с применёнными оптимальными уставками
    """
    prot_dict, new_prot_dict_id = get_protection_dict(mdl, two_stages)

    study = optuna.create_study(direction="minimize")
    study.optimize(
        lambda trial: objective_third(
            trial, mdl, submdl_dict, prot_dict, new_prot_dict_id,
            two_stages, loss_params, loss_callback
        ),
        n_trials=n_trials,
    )

    best_params = study.best_params
    print(f"Best loss: {study.best_value}")

    for i in range(len(prot_dict)):
        t_min, t_max = min(prot_dict[i]['t']), max(prot_dict[i]['t'])
        if two_stages:
            I0_3 = best_params[f"I0_3_{i}"]
            t_3 = t_min + best_params[f"t_3_step_{i}"] * 0.2
            new_prot_dict_id[i][3].edit(I0=round(I0_3, 1), t=round(t_3, 1))

            I0_4 = best_params[f"I0_4_{i}"]
            t_4 = t_min + best_params[f"t_4_step_{i}"] * 0.2
            new_prot_dict_id[i][4].edit(I0=round(I0_4, 1), t=round(t_4, 1))
        else:
            I0_3 = best_params[f"I0_3_{i}"]
            t_3 = t_min + best_params[f"t_3_step_{i}"] * 0.2
            new_prot_dict_id[i].edit(I0=round(I0_3, 1), t=round(t_3, 1))

    return best_params, mdl
