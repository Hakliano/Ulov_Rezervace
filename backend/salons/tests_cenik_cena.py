from salons.cenik_cena import format_cenik_cena


def test_format_cenik_cena_matrix():
    assert format_cenik_cena(None, None, False) == ''
    assert format_cenik_cena(None, None, True) == ''
    assert format_cenik_cena(500, None, False) == '500 Kč'
    assert format_cenik_cena(500, None, True) == 'Od 500 Kč'
    assert format_cenik_cena(500, 900, False) == '500–900 Kč'
    assert format_cenik_cena(500, 900, True) == '500–900 Kč'
    assert format_cenik_cena(500, 500, False) == '500 Kč'
    assert format_cenik_cena(500, 500, True) == 'Od 500 Kč'
    assert format_cenik_cena(900, 500, False) == '500–900 Kč'
    assert format_cenik_cena(None, 900, False) == ''
    assert format_cenik_cena(0, None, False) == 'Zdarma'
    assert format_cenik_cena(0, None, True) == 'Zdarma'
    assert format_cenik_cena(0, 900, False) == 'Zdarma'
