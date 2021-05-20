from random import Random
from typing import Tuple
from unittest.mock import MagicMock

import pytest

from randovania.game_description import default_database
from randovania.game_description.assignment import PickupTarget
from randovania.game_description.item.item_category import ItemCategory
from randovania.game_description.resources.item_resource_info import ItemResourceInfo
from randovania.game_description.resources.pickup_entry import PickupEntry, ResourceLock, PickupModel, \
    ConditionalResources, ResourceConversion
from randovania.game_description.resources.pickup_index import PickupIndex
from randovania.games.game import RandovaniaGame
from randovania.games.prime.patcher_file_lib import pickup_exporter
from randovania.generator.item_pool import pickup_creator
from randovania.interface_common.players_configuration import PlayersConfiguration
from randovania.layout.major_item_state import MajorItemState
from randovania.layout.pickup_model import PickupModelStyle, PickupModelDataSource


def test_get_single_hud_text_all_major_items(echoes_item_database, echoes_resource_database):
    memo_data = default_database.default_prime2_memo_data()

    # Run
    for item in echoes_item_database.major_items.values():
        pickup = pickup_creator.create_major_item(item, MajorItemState(), False, echoes_resource_database, None, False)

        result = pickup_exporter._get_all_hud_text(pickup_exporter._conditional_resources_for_pickup(pickup),
                                                   memo_data)
        for i, progression in enumerate(pickup.progression):
            assert progression[0].long_name in result[i]
        assert result
        for line in result:
            assert len(line) > 10
            assert isinstance(line, str)


@pytest.mark.parametrize("order", [
    ("X", "Y"),
    ("Y", "X"),
    ("Y", "Z"),
])
def test_calculate_hud_text(order: Tuple[str, str]):
    # Setup
    resource_a = ItemResourceInfo(1, "A", "A", 10, None)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)

    pickup_x = PickupEntry("A", 1, ItemCategory.TEMPLE_KEY, ItemCategory.KEY,
                           progression=(
                               ((resource_a, 1),)
                           ))
    pickup_y = PickupEntry("Y", 2, ItemCategory.SUIT, ItemCategory.LIFE_SUPPORT,
                           progression=(
                               (resource_b, 1),
                               (resource_a, 5),
                           ))
    pickup_z = PickupEntry("Z", 2, ItemCategory.SUIT, ItemCategory.LIFE_SUPPORT,
                           progression=(
                               (resource_a, 1),
                               (resource_b, 5),
                           ))

    memo_data = {
        "A": "You got {A} of A",
        "B": "You found {B} of B",
    }
    pickups = {
        "X": pickup_x,
        "Y": pickup_y,
        "Z": pickup_z,
    }

    # Run
    result = pickup_exporter._calculate_hud_text(pickups[order[0]], pickups[order[1]],
                                                 PickupModelStyle.HIDE_ALL, memo_data)

    # Assert
    if order[1] == "Y":
        assert result == ["You found 1 of B"]
    elif order[1] == "X":
        assert result == ["You got 1 of A", "You got 1 of A"]
    else:
        assert result == ["You got 1 of A", "You found 5 of B"]


@pytest.mark.parametrize("model_style", PickupModelStyle)
def test_create_pickup_list(model_style: PickupModelStyle, empty_patches):
    # Setup
    has_scan_text = model_style in {PickupModelStyle.ALL_VISIBLE, PickupModelStyle.HIDE_MODEL}
    rng = Random(5000)

    model_0 = MagicMock(spec=PickupModel)
    model_1 = MagicMock(spec=PickupModel)
    model_2 = MagicMock(spec=PickupModel)
    useless_model = PickupModel(
        game=RandovaniaGame.PRIME2,
        name="EnergyTransferModule",
    )

    useless_resource = ItemResourceInfo(0, "Useless", "Useless", 10, None)
    resource_a = ItemResourceInfo(1, "A", "A", 10, None)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)
    pickup_a = PickupEntry("P-A", model_1, ItemCategory.TEMPLE_KEY, ItemCategory.KEY,
                           progression=((resource_a, 1),),
                           )
    pickup_b = PickupEntry("P-B", model_2, ItemCategory.SUIT, ItemCategory.LIFE_SUPPORT,
                           progression=((resource_b, 1),
                                        (resource_a, 5)), )
    pickup_c = PickupEntry("P-C", model_2, ItemCategory.EXPANSION, ItemCategory.MISSILE_RELATED,
                           progression=tuple(),
                           extra_resources=((resource_b, 2), (resource_a, 1)),
                           unlocks_resource=True,
                           resource_lock=ResourceLock(resource_a, resource_a, useless_resource))

    useless_pickup = PickupEntry("P-Useless", model_0, ItemCategory.ETM, ItemCategory.ETM,
                                 progression=((useless_resource, 1),))
    patches = empty_patches.assign_pickup_assignment({
        PickupIndex(0): PickupTarget(pickup_a, 0),
        PickupIndex(2): PickupTarget(pickup_b, 0),
        PickupIndex(3): PickupTarget(pickup_a, 0),
        PickupIndex(4): PickupTarget(pickup_c, 0),
    })
    creator = pickup_exporter.PickupExporterSolo(pickup_exporter.GenericAcquiredMemo())

    # Run
    result = pickup_exporter.export_all_indices(
        patches,
        PickupTarget(useless_pickup, 0),
        5,
        rng,
        model_style,
        PickupModelDataSource.ETM,
        creator,
        pickup_creator.create_visual_etm(),
    )

    # Assert
    assert len(result) == 5
    assert result[0] == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(0),
        scan_text="P-A" if has_scan_text else "Unknown item",
        hud_text=["A acquired!"] if model_style != PickupModelStyle.HIDE_ALL else ['Unknown item acquired!'],
        conditional_resources=[ConditionalResources("A", None, ((resource_a, 1),))],
        conversion=[],
        model=model_1 if model_style == PickupModelStyle.ALL_VISIBLE else useless_model,
    )
    assert result[1] == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(1),
        scan_text="P-Useless" if has_scan_text else "Unknown item",
        hud_text=["Useless acquired!"] if model_style != PickupModelStyle.HIDE_ALL else ['Unknown item acquired!'],
        conditional_resources=[ConditionalResources("Useless", None, ((useless_resource, 1),))],
        conversion=[],
        model=model_0 if model_style == PickupModelStyle.ALL_VISIBLE else useless_model,
    )
    assert result[2] == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(2),
        scan_text="P-B. Provides the following in order: B, A" if has_scan_text else "Unknown item",
        hud_text=["B acquired!", "A acquired!"] if model_style != PickupModelStyle.HIDE_ALL else [
            'Unknown item acquired!', 'Unknown item acquired!'],
        conditional_resources=[
            ConditionalResources("B", None, ((resource_b, 1),)),
            ConditionalResources("A", resource_b, ((resource_a, 5),)),
        ],
        conversion=[],
        model=model_2 if model_style == PickupModelStyle.ALL_VISIBLE else useless_model,
    )
    assert result[3] == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(3),
        scan_text="P-A" if has_scan_text else "Unknown item",
        hud_text=["A acquired!"] if model_style != PickupModelStyle.HIDE_ALL else ['Unknown item acquired!'],
        conditional_resources=[ConditionalResources("A", None, ((resource_a, 1),))],
        conversion=[],
        model=model_1 if model_style == PickupModelStyle.ALL_VISIBLE else useless_model,
    )
    assert result[4] == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(4),
        scan_text="P-C. Provides 2 B and 1 A" if has_scan_text else "Unknown item",
        hud_text=["P-C acquired!"] if model_style != PickupModelStyle.HIDE_ALL else ['Unknown item acquired!'],
        conditional_resources=[ConditionalResources("P-C", None, (
            (resource_b, 2), (resource_a, 1),
        ))],
        conversion=[ResourceConversion(source=useless_resource, target=resource_a)],
        model=model_2 if model_style == PickupModelStyle.ALL_VISIBLE else useless_model,
    )


@pytest.mark.skip  # FIXME
@pytest.mark.parametrize("has_memo_data", [False, True])
def test_create_pickup_list_random_data_source(has_memo_data: bool, empty_patches):
    # Setup
    rng = Random(5000)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)

    pickup_a = PickupEntry("A", 1, ItemCategory.TEMPLE_KEY, ItemCategory.KEY, progression=tuple())
    pickup_b = PickupEntry("B", 2, ItemCategory.SUIT, ItemCategory.LIFE_SUPPORT,
                           progression=((resource_b, 1), (resource_b, 1)))
    pickup_c = PickupEntry("C", 2, ItemCategory.EXPANSION, ItemCategory.MISSILE_RELATED, progression=tuple())
    useless_pickup = PickupEntry("Useless", 0, ItemCategory.ETM, ItemCategory.ETM, progression=tuple())

    patches = empty_patches.assign_pickup_assignment({
        PickupIndex(0): PickupTarget(pickup_a, 0),
        PickupIndex(2): PickupTarget(pickup_b, 0),
        PickupIndex(3): PickupTarget(pickup_a, 0),
        PickupIndex(4): PickupTarget(pickup_c, 0),
    })

    if has_memo_data:
        memo_data = {
            "A": "This is an awesome item A",
            "B": "This is B. It is good.",
            "C": "What a nice day to have a C",
            "Useless": "Try again next time",
        }
    else:
        memo_data = {
            name: "{} acquired!".format(name)
            for name in ("A", "B", "C", "Useless")
        }

    creator = pickup_exporter.PickupExporterSolo(memo_data)

    # Run
    result = pickup_exporter.export_all_indices(
        patches,
        PickupTarget(useless_pickup, 0),
        5,
        rng,
        PickupModelStyle.HIDE_ALL,
        PickupModelDataSource.RANDOM,
        creator,
        pickup_creator.create_visual_etm(),
    )

    # Assert
    assert len(result) == 5
    assert result[0] == {
        "pickup_index": 0,
        "model_index": 1,
        "scan": "A",
        "hud_text": [memo_data["A"]],
        "sound_index": 1,
        "jingle_index": 2,
        "resources": [],
        "conditional_resources": [],
        "convert": [],
    }
    assert result[1] == {
        "pickup_index": 1,
        "scan": "A",
        "model_index": 1,
        "hud_text": [memo_data["A"]],
        "sound_index": 1,
        "jingle_index": 2,
        "resources": [],
        "conditional_resources": [],
        "convert": [],
    }
    assert result[2] == {
        "pickup_index": 2,
        "scan": "C",
        "model_index": 2,
        "hud_text": [memo_data["C"], memo_data["C"]],
        "sound_index": 0,
        "jingle_index": 0,
        "resources": [{'amount': 1, 'index': 2}],
        "conditional_resources": [{'item': 2, 'resources': [{'amount': 1, 'index': 2}]}],
        "convert": [],
    }
    assert result[3] == {
        "pickup_index": 3,
        "scan": "B",
        "model_index": 2,
        "hud_text": [memo_data["B"]],
        "sound_index": 0,
        "jingle_index": 1,
        "resources": [],
        "conditional_resources": [],
        "convert": [],
    }
    assert result[4] == {
        "pickup_index": 4,
        "scan": "A",
        "model_index": 1,
        "hud_text": [memo_data["A"]],
        "sound_index": 1,
        "jingle_index": 2,
        "resources": [],
        "conditional_resources": [],
        "convert": [],
    }


def test_pickup_scan_for_progressive_suit(echoes_item_database, echoes_resource_database):
    # Setup
    progressive_suit = echoes_item_database.major_items["Progressive Suit"]
    pickup = pickup_creator.create_major_item(progressive_suit, MajorItemState(), False, echoes_resource_database,
                                              None, False)

    # Run
    result = pickup_exporter._pickup_scan(pickup)

    # Assert
    assert result == "Progressive Suit. Provides the following in order: Dark Suit, Light Suit"


@pytest.mark.parametrize(["item", "ammo", "result"], [
    ("Beam Ammo Expansion", [4, 20], "Beam Ammo Expansion. Provides 4 Dark Ammo, 20 Light Ammo and 1 Item Percentage"),
    ("Missile Expansion", [4], "Missile Expansion. Provides 4 Missiles and 1 Item Percentage"),
])
def test_pickup_scan_for_ammo_expansion(echoes_item_database, echoes_resource_database, item, ammo, result):
    # Setup
    expansion = echoes_item_database.ammo[item]
    pickup = pickup_creator.create_ammo_expansion(expansion, ammo, False, echoes_resource_database)

    # Run
    result = pickup_exporter._pickup_scan(pickup)

    # Assert
    assert result == result


@pytest.fixture(name="pickup_for_create_pickup_data")
def _create_pickup_data():
    resource_a = ItemResourceInfo(1, "A", "A", 10, None)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)
    return PickupEntry("Cake", 1, ItemCategory.TEMPLE_KEY, ItemCategory.KEY,
                       progression=(
                           (resource_a, 1),
                           (resource_b, 1),
                       ))


def test_solo_create_pickup_data(pickup_for_create_pickup_data):
    # Setup
    creator = pickup_exporter.PickupExporterSolo(pickup_exporter.GenericAcquiredMemo())
    model = MagicMock()
    resource_a = ItemResourceInfo(1, "A", "A", 10, None)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)

    # Run
    data = creator.create_details(PickupIndex(10), PickupTarget(pickup_for_create_pickup_data, 0),
                                  pickup_for_create_pickup_data, PickupModelStyle.ALL_VISIBLE,
                                  "Scan Text", model)

    # Assert
    assert data == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(10),
        scan_text="Scan Text",
        hud_text=['A acquired!', 'B acquired!'],
        conditional_resources=[
            ConditionalResources("A", None, ((resource_a, 1),)),
            ConditionalResources("B", resource_a, ((resource_b, 1),)),
        ],
        conversion=[],
        model=model,
    )


def test_multi_create_pickup_data_for_self(pickup_for_create_pickup_data):
    # Setup
    solo = pickup_exporter.PickupExporterSolo(pickup_exporter.GenericAcquiredMemo())
    creator = pickup_exporter.PickupExporterMulti(solo, MagicMock(), PlayersConfiguration(0, {0: "You", 1: "Someone"}))
    model = MagicMock()
    resource_a = ItemResourceInfo(1, "A", "A", 10, None)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)

    # Run
    data = creator.create_details(PickupIndex(10), PickupTarget(pickup_for_create_pickup_data, 0),
                                  pickup_for_create_pickup_data, PickupModelStyle.ALL_VISIBLE,
                                  "Scan Text", model)

    # Assert
    assert data == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(10),
        scan_text="Your Scan Text",
        hud_text=['A acquired!', 'B acquired!'],
        conditional_resources=[
            ConditionalResources("A", None, ((resource_a, 1),)),
            ConditionalResources("B", resource_a, ((resource_b, 1),)),
        ],
        conversion=[],
        model=model,
    )


def test_multi_create_pickup_data_for_other(pickup_for_create_pickup_data):
    # Setup
    multi = ItemResourceInfo(10, "Multiworld", "Multiworld", 30, None)
    solo = pickup_exporter.PickupExporterSolo(pickup_exporter.GenericAcquiredMemo())
    creator = pickup_exporter.PickupExporterMulti(solo, multi, PlayersConfiguration(0, {0: "You", 1: "Someone"}))
    model = MagicMock()
    resource_a = ItemResourceInfo(1, "A", "A", 10, None)
    resource_b = ItemResourceInfo(2, "B", "B", 10, None)

    # Run
    data = creator.create_details(PickupIndex(10), PickupTarget(pickup_for_create_pickup_data, 1),
                                  pickup_for_create_pickup_data, PickupModelStyle.ALL_VISIBLE,
                                  "Scan Text", model)

    # Assert
    assert data == pickup_exporter.ExportedPickupDetails(
        index=PickupIndex(10),
        scan_text="Someone's Scan Text",
        hud_text=['Sent Cake to Someone!'],
        conditional_resources=[
            ConditionalResources(None, None, ((multi, 11),)),
        ],
        conversion=[],
        model=model,
    )
