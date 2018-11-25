import pytest
import astropy.units as u
from astropy.coordinates import SkyCoord
from astropy.coordinates import Angle

from pocs.utils import dither


def test_dice9_SkyCoord():
    base = SkyCoord("16h52m42.2s -38d37m12s")

    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            pattern=dither.dice9,
                                            pattern_offset=30 * u.arcminute)

    assert isinstance(positions, SkyCoord)
    assert len(positions) == 12
    # postion 0 should be the base position
    assert positions[0].separation(base) < Angle(1e12 * u.degree)
    # With no random offset positions 9, 10, 11 should be the same as 0, 1, 2
    assert positions[0:3].to_string() == positions[9:12].to_string()
    # Position 1 should be 30 arcminute offset from base, in declination direction only
    assert base.spherical_offsets_to(
        positions[1])[0].radian == pytest.approx(Angle(0 * u.degree).radian)
    assert base.spherical_offsets_to(
        positions[1])[1].radian == pytest.approx(Angle(0.5 * u.degree).radian)
    # Position 3 should be 30 arcminute offset from base in RA only.
    assert base.spherical_offsets_to(
        positions[3])[0].radian == pytest.approx(Angle(0.5 * u.degree).radian)
    assert base.spherical_offsets_to(
        positions[3])[1].radian == pytest.approx(Angle(0 * u.degree).radian)


def test_dice9_string():
    base = "16h52m42.2s -38d37m12s"

    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            pattern=dither.dice9,
                                            pattern_offset=30 * u.arcminute)

    base = SkyCoord(base)

    assert isinstance(positions, SkyCoord)
    assert len(positions) == 12
    # postion 0 should be the base position
    assert positions[0].separation(base) < Angle(1e12 * u.degree)
    # With no random offset positions 9, 10, 11 should be the same as 0, 1, 2
    assert positions[0:3].to_string() == positions[9:12].to_string()
    # Position 1 should be 30 arcminute offset from base, in declination direction only
    assert base.spherical_offsets_to(
        positions[1])[0].radian == pytest.approx(Angle(0 * u.degree).radian)
    assert base.spherical_offsets_to(
        positions[1])[1].radian == pytest.approx(Angle(0.5 * u.degree).radian)
    # Position 3 should be 30 arcminute offset from base in RA only.
    assert base.spherical_offsets_to(
        positions[3])[0].radian == pytest.approx(Angle(0.5 * u.degree).radian)
    assert base.spherical_offsets_to(
        positions[3])[1].radian == pytest.approx(Angle(0 * u.degree).radian)


def test_dice9_bad_base_position():
    with pytest.raises(ValueError):
        dither.get_dither_positions(base_position=42,
                                    num_positions=42,
                                    pattern=dither.dice9,
                                    pattern_offset=300 * u.arcsecond)


def test_dice9_random():
    base = SkyCoord("16h52m42.2s -38d37m12s")

    # Offsets don't have units so added as arcseconds
    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            pattern=dither.dice9,
                                            pattern_offset=30 * 60,
                                            random_offset=30)

    assert isinstance(positions, SkyCoord)
    assert len(positions) == 12
    # postion 0 should be the base position
    assert positions[0].separation(base) < Angle(30 * 2**0.5 * u.arcsecond)

    angle_0 = Angle(0 * u.degree).radian
    angle_05 = Angle(0.5 * u.degree).radian
    angle_30 = Angle(30 * u.arcsecond).radian
    position_1_offset = base.spherical_offsets_to(positions[1])
    position_3_offset = base.spherical_offsets_to(positions[3])

    # Position 1 should be 30 arcminute offset from base, in declination direction only
    assert position_1_offset[0].radian == pytest.approx(angle_0, abs=angle_30)
    assert position_1_offset[1].radian == pytest.approx(angle_05, abs=angle_30)

    # Position 3 should be 30 arcminute offset from base in RA only.
    assert position_3_offset[0].radian == pytest.approx(angle_05, abs=angle_30)
    assert position_3_offset[1].radian == pytest.approx(angle_0, abs=angle_30)


def test_random():
    base = SkyCoord("16h52m42.2s -38d37m12s")

    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            random_offset=30 * u.arcsecond)
    assert isinstance(positions, SkyCoord)
    assert len(positions) == 12

    angle_0 = Angle(0 * u.degree).radian
    angle_30 = Angle(30 * u.arcsecond).radian
    position_0_offset = base.spherical_offsets_to(positions[0])
    position_1_offset = base.spherical_offsets_to(positions[1])

    assert position_0_offset[0].radian == pytest.approx(angle_0, abs=angle_30)
    assert position_0_offset[1].radian == pytest.approx(angle_0, abs=angle_30)

    assert position_1_offset[0].radian == pytest.approx(angle_0, abs=angle_30)
    assert position_1_offset[1].radian == pytest.approx(angle_0, abs=angle_30)


def test_dice5():
    base = SkyCoord("16h52m42.2s -38d37m12s")

    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            pattern=dither.dice5,
                                            pattern_offset=30 * u.arcminute)

    assert isinstance(positions, SkyCoord)
    assert len(positions) == 12
    # postion 0 should be the base position
    assert positions[0].separation(base) < Angle(1e12 * u.degree)
    # With no random offset positions 5, 6, 7 should be the same as 0, 1, 2
    assert positions[0:3].to_string() == positions[5:8].to_string()
    # Position 1 should be 30 arcminute offset from base, in RA and dec
    assert base.spherical_offsets_to(
        positions[1])[0].radian == pytest.approx(Angle(0.5 * u.degree).radian)
    assert base.spherical_offsets_to(
        positions[1])[1].radian == pytest.approx(Angle(0.5 * u.degree).radian)
    # Position 3 should be 30 arcminute offset from base in RA and dec
    assert base.spherical_offsets_to(positions[3])[0].radian == pytest.approx(
        Angle(-0.5 * u.degree).radian)
    assert base.spherical_offsets_to(positions[3])[1].radian == pytest.approx(
        Angle(-0.5 * u.degree).radian)


def test_custom_pattern():
    base = SkyCoord("16h52m42.2s -38d37m12s")
    cross = ((0, 0),
             (0, 1),
             (1, 0),
             (0, -1),
             (-1, 0))

    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            pattern=cross,
                                            pattern_offset=1800 * u.arcsecond)

    assert isinstance(positions, SkyCoord)
    assert len(positions) == 12
    # postion 0 should be the base position
    assert positions[0].separation(base) < Angle(1e12 * u.degree)
    # With no random offset positions 5, 6, 7 should be the same as 0, 1, 2
    assert positions[0:3].to_string() == positions[5:8].to_string()
    # Position 3 should be 30 arcminute offset from base, in declination direction only
    assert base.spherical_offsets_to(
        positions[3])[0].radian == pytest.approx(Angle(0 * u.degree).radian)
    assert base.spherical_offsets_to(positions[3])[1].radian == pytest.approx(
        Angle(-0.5 * u.degree).radian)
    # Position 4 should be 30 arcminute offset from base in RA only.
    assert base.spherical_offsets_to(positions[4])[0].radian == pytest.approx(
        Angle(-0.5 * u.degree).radian)
    assert base.spherical_offsets_to(
        positions[4])[1].radian == pytest.approx(Angle(0 * u.degree).radian)


@pytest.mark.mpl_image_compare(baseline_dir='baseline_images')
def test_plot_dither(tmpdir):
    base = SkyCoord("16h52m42.2s -38d37m12s")
    positions = dither.get_dither_positions(base_position=base,
                                            num_positions=12,
                                            pattern=dither.dice9,
                                            pattern_offset=30 * u.arcminute)

    dither_figure = dither.plot_dither_pattern(positions)
    return dither_figure
