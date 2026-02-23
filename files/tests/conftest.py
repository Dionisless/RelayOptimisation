"""
Фикстуры pytest для тестирования пайплайна оптимизации релейной защиты.
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
import kar_mrtkz as ktkz
import kar_analyse as kanl
import kar_optimisation_pypeline as kop


@pytest.fixture(scope="module")
def base_mdl():
    """
    Тестовая модель: 5 узлов, 6 линий, 4 ступени ТЗНП на каждой ветви.

    Используется как неизменяемая база для тестов; каждый тест,
    требующий модификации модели, должен работать с копией через ktkz.duplicate_mdl().
    """
    return ktkz.base_model()


@pytest.fixture(scope="module")
def simple_submdl_dict(base_mdl):
    """
    Малый словарь подрежимов (1 пояс, 1 линия в переборе, шаг 0.5, только A0).

    Используется в быстрых тестах, где полный перебор не нужен.
    """
    mdl_copy = ktkz.duplicate_mdl(base_mdl)
    return kanl.generate_submodels(
        mdl_copy,
        max_belt_range=1,
        num_of_enum_lines=1,
        step=0.5,
        kz_types=['A0']
    )
