"""
Тесты функций анализа релейной защиты (kar_analyse.py).

Покрытие: generate_submodels, analyze_relay_protections, ML_func, def_score.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import kar_mrtkz as ktkz
import kar_analyse as kanl
import kar_optimisation_pypeline as kop


# ---------------------------------------------------------------------------
# generate_submodels
# ---------------------------------------------------------------------------

def test_generate_submodels_returns_dict(base_mdl):
    """generate_submodels возвращает словарь."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    result = kanl.generate_submodels(mdl, max_belt_range=1, num_of_enum_lines=1,
                                     step=0.5, kz_types=['A0'])
    assert isinstance(result, dict), "Результат должен быть dict"


def test_generate_submodels_keys(base_mdl):
    """Каждая запись содержит обязательные ключи."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    result = kanl.generate_submodels(mdl, max_belt_range=1, num_of_enum_lines=1,
                                     step=0.5, kz_types=['A0'])
    required_keys = {'id', 'line_kz', 'kz_type', 'percent', 'p_off'}
    for sm_id, row in result.items():
        assert required_keys.issubset(row.keys()), (
            f"Запись {sm_id} не содержит ключи: {required_keys - row.keys()}"
        )


def test_generate_submodels_nonempty(base_mdl):
    """generate_submodels возвращает непустой словарь."""
    mdl = ktkz.duplicate_mdl(base_mdl)
    result = kanl.generate_submodels(mdl, max_belt_range=1, num_of_enum_lines=1,
                                     step=0.5, kz_types=['A0'])
    assert len(result) > 0, "Словарь подрежимов не должен быть пустым"


# ---------------------------------------------------------------------------
# analyze_relay_protections
# ---------------------------------------------------------------------------

def test_analyze_relay_protections_returns_dict(base_mdl, simple_submdl_dict):
    """analyze_relay_protections возвращает словарь."""
    result = kanl.analyze_relay_protections(
        base_mdl, simple_submdl_dict, log=False, print_G=False
    )
    assert isinstance(result, dict), "Результат должен быть dict"


def test_analyze_relay_protections_result_fields(base_mdl, simple_submdl_dict):
    """Каждая запись содержит обязательные поля."""
    result = kanl.analyze_relay_protections(
        base_mdl, simple_submdl_dict, log=False, print_G=False
    )
    required_keys = {'id', 't', 'submdl_id', 'line_kz', 'line', 'k_ch'}
    for work_id, work in result.items():
        assert required_keys.issubset(work.keys()), (
            f"Запись {work_id} не содержит ключи: {required_keys - work.keys()}"
        )


def test_analyze_relay_protections_ids(base_mdl, simple_submdl_dict):
    """Все id ∈ {-7, -666} или > 0."""
    result = kanl.analyze_relay_protections(
        base_mdl, simple_submdl_dict, log=False, print_G=False
    )
    for work_id, work in result.items():
        wid = work.get('id')
        assert wid in (-7, -666) or wid > 0, (
            f"Неожиданный id={wid} в записи {work_id}"
        )


# ---------------------------------------------------------------------------
# ML_func
# ---------------------------------------------------------------------------

def test_ml_func_returns_number(base_mdl, simple_submdl_dict):
    """ML_func возвращает число."""
    loss = kanl.ML_func(base_mdl, simple_submdl_dict, show_result=False)
    assert isinstance(loss, (int, float)), "ML_func должна возвращать число"


def test_ml_func_nonnegative(base_mdl, simple_submdl_dict):
    """Потери >= 0 при штрафе off=0."""
    loss = kanl.ML_func(base_mdl, simple_submdl_dict, off=0, show_result=False)
    assert loss >= 0, f"Потери не могут быть отрицательными при off=0, получено {loss}"


def test_ml_func_extended_result(base_mdl, simple_submdl_dict):
    """При extended_result=True возвращается словарь с ключами loss и non_select_count."""
    result = kanl.ML_func(base_mdl, simple_submdl_dict,
                          extended_result=True, show_result=False)
    assert isinstance(result, dict), "При extended_result=True должен возвращаться dict"
    assert 'loss' in result, "Ключ 'loss' должен быть в расширенном результате"
    assert 'non_select_count' in result, "Ключ 'non_select_count' должен быть в расширенном результате"


# ---------------------------------------------------------------------------
# def_score
# ---------------------------------------------------------------------------

def test_def_score_no_off_penalty(base_mdl, simple_submdl_dict):
    """def_score возвращает положительное число при наличии -666."""
    prot_work = kanl.analyze_relay_protections(
        base_mdl, simple_submdl_dict, log=False, print_G=False
    )
    no_off_count = sum(1 for w in prot_work.values() if w.get('id') == -666)
    if no_off_count == 0:
        pytest.skip("Нет неотключений для проверки этого теста")
    loss = kanl.def_score(base_mdl, prot_work, no_off=10, off=0,
                          non_select=0, show_result=False)
    assert loss >= no_off_count * 10, (
        f"Штраф за неотключения должен быть >= {no_off_count * 10}, получено {loss}"
    )


def test_def_score_non_select_penalty(base_mdl, simple_submdl_dict):
    """def_score корректно считает неселективные срабатывания."""
    prot_work = kanl.analyze_relay_protections(
        base_mdl, simple_submdl_dict, log=False, print_G=False
    )
    result = kanl.def_score(base_mdl, prot_work, non_select=1,
                            no_off=0, off=0, show_result=False,
                            extended_result=True)
    non_select_count = result.get('non_select_count', 0)
    assert isinstance(non_select_count, int), "non_select_count должен быть int"
    assert non_select_count >= 0, "non_select_count должен быть >= 0"
