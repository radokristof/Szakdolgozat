def compare_tuple(tpl1: tuple, tpl2: tuple) -> bool:
    """
    Compare two tuples. Return True if their values are the same, only the order is different.
    :param tpl1: The first tuple to compare
    :param tpl2: The second tuple to compare
    :return: True if the tuples are the same, False if they are not
    """
    return sorted(tpl1) == sorted(tpl2)


def compare_list_tuples(lst: list, tpl: tuple) -> bool:
    """
    Compare a list of tuples with a tuple. Return True if the tuple is in the list.
    :param lst: The list of tuples to compare
    :param tpl: The tuple to compare
    :return: True if the tuple is in the list, False if it is not
    """
    for elem in lst:
        if compare_tuple(elem, tpl):
            return True
    return False
