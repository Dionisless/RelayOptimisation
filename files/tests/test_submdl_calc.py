"""
Тесты DSL-калькулятора подрежимов (submdl_calc_main и вспомогательных функций).

Проверяет:
- tokenize_expression: разбор выражений с минусом и именами, содержащими дефис
- separate_by_plas: знаки (+1/-1) при возврате групп
- subtract_submdl_dicts: корректное вычитание подрежимов
- submdl_calc_main: оператор '-' между группами (внешний минус)
- find_const_in_buscets: '(ЛИНИИКЗ[ВСЕ]-ЛИНИИКЗ[PS1-PS2])' внутри скобок
- find_p_off_summ_in_buscets: '(ПОЯС[1]-ОБЪЕКТЫ[...])' внутри скобок
- '+' (объединение) и базовая генерация по ЛИНИИКЗ
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import kar_mrtkz as ktkz
import kar_analyse as kanl


@pytest.fixture(scope='module')
def mdl():
    return ktkz.base_model()


# ---------------------------------------------------------------------------
# Тесты tokenize_expression
# ---------------------------------------------------------------------------

def test_tokenize_minus():
    """Оператор '-' на верхнем уровне разбивается как отдельный токен."""
    result = kanl.tokenize_expression('A[1]-B[2]')
    assert result == ['A[1]', '-', 'B[2]']


def test_tokenize_dash_in_brackets():
    """Дефис внутри квадратных скобок не является оператором."""
    result = kanl.tokenize_expression('ЛИНИИКЗ[PS1-PS2]')
    assert result == ['ЛИНИИКЗ[PS1-PS2]']


def test_tokenize_minus_and_star():
    """Смешанное выражение: '*' и '-' на верхнем уровне."""
    result = kanl.tokenize_expression('A[1]*B-C[2]*D')
    assert result == ['A[1]', '*', 'B', '-', 'C[2]', '*', 'D']


# ---------------------------------------------------------------------------
# Тесты separate_by_plas
# ---------------------------------------------------------------------------

def test_separate_sign_plus():
    """'+' создаёт группу со знаком +1."""
    result = kanl.separate_by_plas('A+B')
    assert result == [(1, ['A']), (1, ['B'])]


def test_separate_sign_minus():
    """'-' создаёт группу со знаком -1."""
    result = kanl.separate_by_plas('A+B-C')
    assert result == [(1, ['A']), (1, ['B']), (-1, ['C'])]


def test_separate_sign_first_group_positive():
    """Первая группа всегда имеет знак +1."""
    result = kanl.separate_by_plas('X*Y*Z')
    assert len(result) == 1
    assert result[0][0] == 1
    assert result[0][1] == ['X', 'Y', 'Z']


# ---------------------------------------------------------------------------
# Тест subtract_submdl_dicts
# ---------------------------------------------------------------------------

def test_subtract_submdl_dicts():
    """subtract_submdl_dicts: вычитает записи по ключу (line_kz, kz_type, percent, frozenset(p_off))."""
    pos = {
        1: {'id': 1, 'line_kz': 'L1', 'kz_type': 'A0', 'percent': 0.0, 'p_off': ()},
        2: {'id': 2, 'line_kz': 'L2', 'kz_type': 'A0', 'percent': 0.0, 'p_off': ()},
        3: {'id': 3, 'line_kz': 'L1', 'kz_type': 'A0', 'percent': 0.5, 'p_off': ('X',)},
    }
    neg = {
        1: {'id': 1, 'line_kz': 'L1', 'kz_type': 'A0', 'percent': 0.0, 'p_off': ()},
    }
    result = kanl.subtract_submdl_dicts(pos, neg)
    assert len(result) == 2
    keys = {(e['line_kz'], e['kz_type'], e['percent'], frozenset(e['p_off'])) for e in result.values()}
    assert ('L2', 'A0', 0.0, frozenset()) in keys
    assert ('L1', 'A0', 0.5, frozenset({'X'})) in keys
    assert ('L1', 'A0', 0.0, frozenset()) not in keys


def test_subtract_submdl_dicts_empty_neg():
    """Вычитание пустого словаря возвращает полный positive_dict."""
    pos = {
        1: {'id': 1, 'line_kz': 'L1', 'kz_type': 'A0', 'percent': 0.0, 'p_off': ()},
        2: {'id': 2, 'line_kz': 'L2', 'kz_type': 'A0', 'percent': 0.0, 'p_off': ()},
    }
    result = kanl.subtract_submdl_dicts(pos, {})
    assert len(result) == 2


# ---------------------------------------------------------------------------
# Тесты submdl_calc_main: оператор '-' между группами (внешний минус)
# ---------------------------------------------------------------------------

def test_liniekz_basic(mdl):
    """ЛИНИИКЗ[ВСЕ]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0] генерирует записи для всех линий."""
    expr = 'ЛИНИИКЗ[ВСЕ]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]'
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    all_lines = [p.name for p in mdl.bp]
    # Шаг 0.5: позиции 0%, 50%, 100% → 3 позиции
    assert len(result) == len(all_lines) * 3
    assert set(e['line_kz'] for e in result.values()) == set(all_lines)


def test_liniekz_minus_outer(mdl):
    """Внешний '-': ЛИНИИКЗ[ВСЕ] - ЛИНИИКЗ[PS1-PS2] исключает линию PS1-PS2."""
    expr = ('ЛИНИИКЗ[ВСЕ]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]'
            ' - ЛИНИИКЗ[PS1-PS2]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]')
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    all_lines = [p.name for p in mdl.bp]
    expected_lines = set(all_lines) - {'PS1-PS2'}
    assert set(e['line_kz'] for e in result.values()) == expected_lines
    assert len(result) == len(expected_lines) * 3
    assert all(e['line_kz'] != 'PS1-PS2' for e in result.values())


def test_minus_outer_перебор(mdl):
    """ОБЪЕКТЫ*ПЕРЕБОР[2] - ОБЪЕКТЫ*ПЕРЕБОР[1]: остаются только 2-линейные комбинации."""
    expr = ('ОБЪЕКТЫ[PS1-PS2,PS4-PS5]*ЛИНИИКЗ[PS2-PS3]*ТИПКЗ[AB0]*ШАГ[0.5]*ПЕРЕБОР[2]'
            ' - ОБЪЕКТЫ[PS1-PS2,PS4-PS5]*ЛИНИИКЗ[PS2-PS3]*ТИПКЗ[AB0]*ШАГ[0.5]*ПЕРЕБОР[1]')
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    # ПЕРЕБОР[2] из 2 объектов даёт 1 комбинацию × 3 позиции = 3 записи
    # ПЕРЕБОР[1] из 2 объектов даёт 2 комбинации × 3 позиции = 6 записей
    # Вычитание: ключи p_off разные (frozenset из 1 vs 2 объектов) → вычитания нет
    # Остаётся только ПЕРЕБОР[2] = 3 записи
    assert len(result) == 3
    for e in result.values():
        assert len(e['p_off']) == 2


def test_plus_union(mdl):
    """'+': объединение двух наборов подрежимов по разным линиям КЗ."""
    expr = ('ЛИНИИКЗ[PS1-PS2]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]'
            '+ЛИНИИКЗ[PS1-PS3]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]')
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    lines_in_result = set(e['line_kz'] for e in result.values())
    assert 'PS1-PS2' in lines_in_result
    assert 'PS1-PS3' in lines_in_result
    # PS1-PS2: 3 позиции + PS1-PS3: 3 позиции = 6 записей
    assert len(result) == 6


# ---------------------------------------------------------------------------
# Тесты submdl_calc_main: оператор '-' внутри скобок
# ---------------------------------------------------------------------------

def test_liniekz_all_minus_one_in_brackets(mdl):
    """(ЛИНИИКЗ[ВСЕ]-ЛИНИИКЗ[PS1-PS2])*...: PS1-PS2 исключена из line_kz."""
    expr = '(ЛИНИИКЗ[ВСЕ]-ЛИНИИКЗ[PS1-PS2])*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]'
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    all_lines = set(p.name for p in mdl.bp)
    expected = all_lines - {'PS1-PS2'}
    assert set(e['line_kz'] for e in result.values()) == expected
    assert all(e['line_kz'] != 'PS1-PS2' for e in result.values())
    assert len(result) == len(expected) * 3


def test_poyaz_minus_objects_in_brackets(mdl):
    """(ПОЯС[1]-ОБЪЕКТЫ[PS1-PS2,PS4-PS5])*...: p_off = belt1 минус исключённые объекты."""
    expr = '(ПОЯС[1]-ОБЪЕКТЫ[PS1-PS2,PS4-PS5])*ТИПКЗ[A0]*ЛИНИИКЗ[PS1-PS3]*ШАГ[0.5]*ПЕРЕБОР[1]'
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    belt1 = set(kanl.belt(mdl, belt=['1'], line='PS1-PS3'))
    excluded = {'PS1-PS2', 'PS4-PS5'}
    expected_p_off = belt1 - excluded
    # Каждый p_off ∈ expected_p_off должен встречаться в результатах
    result_p_offs = set(e['p_off'][0] for e in result.values() if e['p_off'])
    assert result_p_offs == expected_p_off
    # PS1-PS2 и PS4-PS5 не должны встречаться в p_off
    for e in result.values():
        assert 'PS1-PS2' not in e['p_off']
        assert 'PS4-PS5' not in e['p_off']


def test_poyaz_plus_inducts_in_brackets(mdl):
    """(ПОЯС[1]+ИНДУКЦ)*...: p_off = объединение belt1 и индукционно-связанных линий."""
    expr = '(ПОЯС[1]+ИНДУКЦ)*ТИПКЗ[A0]*ЛИНИИКЗ[PS1-PS4]*ШАГ[0.5]*ПЕРЕБОР[1]'
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    belt1 = set(kanl.belt(mdl, belt=['1'], line='PS1-PS4'))
    induct_lines = set(kanl.induct(mdl, 'PS1-PS4'))
    expected_p_off = belt1 | induct_lines
    result_p_offs = set(e['p_off'][0] for e in result.values() if e['p_off'])
    assert result_p_offs == expected_p_off
    # Количество: len(expected_p_off) вариантов * 3 позиции
    assert len(result) == len(expected_p_off) * 3


# ---------------------------------------------------------------------------
# Тест обязательных полей результата
# ---------------------------------------------------------------------------

def test_result_fields(mdl):
    """Каждая запись submdl_calc_main содержит обязательные поля."""
    expr = 'ЛИНИИКЗ[PS1-PS2]*ШАГ[0.5]*ПЕРЕБОР[0]*ТИПКЗ[A0]'
    result = kanl.submdl_calc_main(mdl, expr, submdl_dict={})
    required = {'id', 'line_kz', 'kz_type', 'percent', 'p_off'}
    for entry in result.values():
        assert required.issubset(entry.keys())
