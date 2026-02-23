"""
Тесты основного пайплайна оптимизации релейной защиты.

Покрытие: disable_prot, to_submdl, calc_first_stage, first_stage_update,
          calc_second_stage, second_stage_update, optimize_protection_times,
          полный 2-ступенчатый пайплайн.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import optuna
import kar_mrtkz as ktkz
import kar_analyse as kanl
import kar_optimisation_pypeline as kop

optuna.logging.set_verbosity(optuna.logging.WARNING)


# ---------------------------------------------------------------------------
# disable_prot
# ---------------------------------------------------------------------------

def test_disable_prot(base_mdl):
    """Все защиты получают I0=99999999 и t=1000 после disable_prot."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    for d in mdl.bd:
        assert d.I0 == 99999999, f"I0 должен быть 99999999, получено {d.I0}"
        assert d.t == 1000, f"t должен быть 1000, получено {d.t}"


# ---------------------------------------------------------------------------
# to_submdl
# ---------------------------------------------------------------------------

def test_to_submdl_structure(simple_submdl_dict, base_mdl):
    """to_submdl создаёт подмодель с узлом KZ."""
    row = next(iter(simple_submdl_dict.values()))
    submdl = kanl.to_submdl(base_mdl, row)
    node_names = [q.name for q in submdl.bq]
    assert 'KZ' in node_names, "Подмодель должна содержать узел 'KZ'"


def test_to_submdl_calculated(simple_submdl_dict, base_mdl):
    """to_submdl возвращает рассчитанную подмодель (bn не пустой)."""
    row = next(iter(simple_submdl_dict.values()))
    submdl = kanl.to_submdl(base_mdl, row)
    assert len(submdl.bn) > 0, "После Calc() подмодель должна иметь объекты несимметрии (bn)"


# ---------------------------------------------------------------------------
# calc_first_stage
# ---------------------------------------------------------------------------

def test_calc_first_stage_sets_i0(base_mdl, simple_submdl_dict):
    """calc_first_stage устанавливает I0 > 100 для всех защит 1 ступени."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    stage1_defs = [d for d in mdl.bd if d.stage == 1]
    assert len(stage1_defs) > 0, "Должны быть защиты 1 ступени"
    for d in stage1_defs:
        assert d.I0 > 100, f"I0 ступени 1 должен быть > 100, получено {d.I0}"


def test_calc_first_stage_timing(base_mdl, simple_submdl_dict):
    """Время срабатывания 1 ступени должно быть 0."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    for d in mdl.bd:
        if d.stage == 1:
            assert d.t == 0, f"Время 1 ступени должно быть 0, получено {d.t}"


# ---------------------------------------------------------------------------
# first_stage_update
# ---------------------------------------------------------------------------

def test_first_stage_no_mistrip(base_mdl, simple_submdl_dict):
    """После first_stage_update нет ложных срабатываний t=0 на чужих линиях."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    prot_work = kanl.analyze_relay_protections(mdl, simple_submdl_dict, log=False, print_G=False)
    for work_id, work in prot_work.items():
        if work.get('t') == 0 and work.get('id') not in (-7, -666):
            line = work.get('line', '')
            line_kz = work.get('line_kz', '')
            assert line in ('q1-kz', 'kz-q2', line_kz), (
                f"Ступень t=0 сработала на чужой линии: {line} при КЗ на {line_kz}"
            )


# ---------------------------------------------------------------------------
# calc_second_stage
# ---------------------------------------------------------------------------

def test_calc_second_stage_sets_i0(base_mdl, simple_submdl_dict):
    """calc_second_stage устанавливает конечный I0 для защит 2 ступени."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    kop.calc_second_stage(mdl, simple_submdl_dict)
    stage2_defs = [d for d in mdl.bd if d.stage == 2]
    assert len(stage2_defs) > 0, "Должны быть защиты 2 ступени"
    for d in stage2_defs:
        assert d.I0 < 99999999, f"I0 ступени 2 не должен быть дефолтным 99999999"


def test_calc_second_stage_timing(base_mdl, simple_submdl_dict):
    """Время срабатывания 2 ступени после calc_second_stage = 1.4 с."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    kop.calc_second_stage(mdl, simple_submdl_dict)
    for d in mdl.bd:
        if d.stage == 2:
            assert abs(d.t - 1.4) < 0.01, f"t ступени 2 должно быть 1.4, получено {d.t}"


# ---------------------------------------------------------------------------
# second_stage_update
# ---------------------------------------------------------------------------

def test_second_stage_reduces_no_off(base_mdl, simple_submdl_dict):
    """После second_stage_update количество неотключений (-666) не увеличивается."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    kop.calc_second_stage(mdl, simple_submdl_dict)

    prot_work_before = kanl.analyze_relay_protections(mdl, simple_submdl_dict, log=False, print_G=False)
    count_before = sum(1 for w in prot_work_before.values() if w.get('id') == -666)

    kop.second_stage_update(mdl, simple_submdl_dict)

    prot_work_after = kanl.analyze_relay_protections(mdl, simple_submdl_dict, log=False, print_G=False)
    count_after = sum(1 for w in prot_work_after.values() if w.get('id') == -666)

    assert count_after <= count_before, (
        f"Кол-во неотключений не должно расти: было {count_before}, стало {count_after}"
    )


# ---------------------------------------------------------------------------
# optimize_protection_times
# ---------------------------------------------------------------------------

def test_optimize_times_returns_dict(base_mdl, simple_submdl_dict):
    """optimize_protection_times возвращает словарь уставок."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    kop.calc_second_stage(mdl, simple_submdl_dict)
    kop.second_stage_update(mdl, simple_submdl_dict)
    result = kop.optimize_protection_times(mdl, simple_submdl_dict, n_trials=5)
    assert isinstance(result, dict), "Результат должен быть словарём"


def test_optimize_times_improves_loss(base_mdl, simple_submdl_dict):
    """optimize_protection_times не ухудшает функцию потерь."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    kop.calc_second_stage(mdl, simple_submdl_dict)
    kop.second_stage_update(mdl, simple_submdl_dict)

    loss_before = kanl.ML_func(mdl, simple_submdl_dict)
    kop.optimize_protection_times(mdl, simple_submdl_dict, n_trials=10)
    loss_after = kanl.ML_func(mdl, simple_submdl_dict)

    assert loss_after <= loss_before + 1e-6, (
        f"Потери не должны расти: было {loss_before:.4f}, стало {loss_after:.4f}"
    )


# ---------------------------------------------------------------------------
# Полный 2-ступенчатый пайплайн
# ---------------------------------------------------------------------------

def test_full_2stage_pipeline(base_mdl, simple_submdl_dict):
    """Полный пайплайн 2 ступени снижает функцию потерь относительно начального состояния."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    loss_initial = kanl.ML_func(mdl, simple_submdl_dict)

    kop.disable_prot(mdl)
    kop.calc_first_stage(mdl, simple_submdl_dict)
    kop.first_stage_update(mdl, simple_submdl_dict)
    kop.calc_second_stage(mdl, simple_submdl_dict)
    kop.second_stage_update(mdl, simple_submdl_dict)
    kop.optimize_protection_times(mdl, simple_submdl_dict, n_trials=10)

    loss_final = kanl.ML_func(mdl, simple_submdl_dict)
    assert loss_final < loss_initial, (
        f"Пайплайн должен снижать потери: начальные {loss_initial:.4f}, финальные {loss_final:.4f}"
    )
