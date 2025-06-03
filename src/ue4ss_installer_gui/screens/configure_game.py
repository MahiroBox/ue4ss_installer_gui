import pathlib
import shutil
import os
import uuid
import subprocess
from typing import Callable, Any

import dearpygui.dearpygui as dpg

from ue4ss_installer_gui import grid, settings, ue4ss, constants, translator, file_io, auto_align
from ue4ss_installer_gui.screens import (
    setup_screen, 
    notification_screen, 
    main_ue4ss_screen, 
    ue4ss_settings_configurator, 
    ue4ss_mods_configurator,
    bp_mod_loader_configurator,
    developer_screen
)
from ue4ss_installer_gui.checks import online_check


def filter_ue4ss_tag(sender, app_data, user_data):
    refresh_ue4ss_tags_combo_box(user_data=user_data)
    refresh_file_to_install_combo_box(user_data)


def filter_ue4ss_file_to_install(sender, app_data, user_data):
    refresh_ue4ss_tags_combo_box(user_data=user_data)
    refresh_file_to_install_combo_box(user_data)


def push_uninstall_successful_screen(user_data):
    notification_screen.push_notification_screen(
        translator.translator.translate("uninstall_succeeded_message_text"),
        pathlib.Path(user_data),
    )


def push_install_successful_screen(user_data):
    if isinstance(user_data, list):
        user_data = user_data[0]
    notification_screen.push_notification_screen(
        translator.translator.translate("install_succeeded_message_text"),
        pathlib.Path(user_data),
    )


def push_uninstall_failed_screen(user_data):
    notification_screen.push_notification_screen(
        translator.translator.translate("uninstall_failed_message_text"),
        pathlib.Path(user_data),
    )


def push_install_failed_screen(user_data):
    notification_screen.push_notification_screen(
        translator.translator.translate("install_failed_message_text"),
        pathlib.Path(user_data),
    )


def refresh_file_to_install_combo_box(user_data):
    filter = dpg.get_value("filter_ue4ss_file_to_install")
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        user_data
    )
    selected_tag = dpg.get_value("tags_combo_box")

    if not game_info or ue4ss.cached_repo_releases_info is None:
        return

    tag_info = next(
        (
            tag
            for tag in ue4ss.cached_repo_releases_info.tags
            if tag.tag == selected_tag
        ),
        None,
    )
    if not tag_info:
        return

    default_items = []

    for asset in tag_info.assets:
        filename = asset.file_name
        lower = filename.lower()
        is_dev = "dev" in lower

        if (game_info.using_developer_version and is_dev) or (
            not game_info.using_developer_version and not is_dev
        ):
            if lower not in ["zcustomgameconfigs.zip", "zmapgenbp.zip"]:
                default_items.append((filename, asset.created_at))

    default_items.sort(key=lambda x: x[1], reverse=True)

    sorted_filenames = [filename for filename, _ in default_items]

    filtered_filenames = [
        filename for filename in sorted_filenames if filter.lower() in filename.lower()
    ]

    if not game_info.using_developer_version:
        portable_enabled = dpg.get_value("portable_version_check_box")

        if portable_enabled:
            filtered_filenames = [
                filename for filename in filtered_filenames if "Standard" in filename
            ]
        else:
            filtered_filenames = [
                filename
                for filename in filtered_filenames
                if "Standard" not in filename
            ]

    if filtered_filenames:
        default_value = (
            game_info.last_installed_version
            if game_info.last_installed_version in filtered_filenames
            else filtered_filenames[0]
        )
        dpg.configure_item(
            "ue4ss_file_to_install_combo_box",
            items=filtered_filenames,
            default_value=default_value,
        )
    else:
        if len(sorted_filenames) > 1:
            default_value = (
                game_info.last_installed_version
                if game_info.last_installed_version in sorted_filenames
                else sorted_filenames[0]
            )
            dpg.configure_item(
                "ue4ss_file_to_install_combo_box",
                items=sorted_filenames,
                default_value=default_value,
            )
        else:
            dpg.configure_item(
                "ue4ss_file_to_install_combo_box",
                items=sorted_filenames,
                default_value="",
            )


def update_game_info_field_from_ui(
    game_directory: str, field_name: str, value, should_save: bool = True
):
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        game_directory
    )
    if game_info:
        setattr(game_info, field_name, value)
        settings.save_game_info_to_settings_file(game_info)


def on_ue4ss_version_tag_combo_box_selected(sender, app_data, user_data):
    update_game_info_field_from_ui(
        user_data, "ue4ss_version", app_data, should_save=False
    )
    refresh_file_to_install_combo_box(user_data)


def on_developer_check_box_toggled(sender, app_data, user_data):
    update_game_info_field_from_ui(user_data, "using_developer_version", app_data)

    if app_data:
        dpg.set_value("portable_version_check_box", False)
        update_game_info_field_from_ui(user_data, "using_portable_version", False)

    refresh_file_to_install_combo_box(user_data)


def on_portable_version_check_box_toggled(sender, app_data, user_data):
    update_game_info_field_from_ui(user_data, "using_portable_version", app_data)

    if app_data:
        dpg.set_value("developer_version_check_box", False)
        update_game_info_field_from_ui(user_data, "using_developer_version", False)

    refresh_file_to_install_combo_box(user_data)


def on_keep_mods_and_settings_check_box_toggled(sender, app_data, user_data):
    update_game_info_field_from_ui(user_data, "using_keep_mods_and_settings", app_data)


def on_using_pre_releases_check_box_toggled(sender, app_data, user_data):
    update_game_info_field_from_ui(user_data, "show_pre_releases", app_data)
    refresh_ue4ss_tags_combo_box(user_data=user_data)
    refresh_file_to_install_combo_box(user_data)


def install_ue4ss_through_zip(user_data):
    file_io.unzip_zip(user_data[1], get_exe_dir_from_game_dir(user_data[0]))
    all_paths_in_zip = file_io.get_paths_of_files_in_zip(user_data[1])
    update_game_info_field_from_ui(user_data[0], "installed_files", all_paths_in_zip)


def delete_all_empty_dirs_in_dir_tree(root: pathlib.Path):
    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()


def uninstall_ue4ss(user_data):
    if isinstance(user_data, list):
        user_data = user_data[0]
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        user_data
    )
    exe_dir = get_exe_dir_from_game_dir(user_data)
    if game_info is None:
        raise RuntimeError("game info is none, uninstall ue4ss function")

    for file_to_delete in game_info.installed_files:
        file_to_delete_actual_path = os.path.normpath(f"{exe_dir}/{file_to_delete}")
        if os.path.isfile(file_to_delete_actual_path):
            os.remove(file_to_delete_actual_path)

    files_to_clean_always = [
        f"{exe_dir}/UE4SS.log",
        f"{exe_dir}/ue4ss/UE4SS.log",
        f"{exe_dir}/ue4ss/imgui.ini",
        f"{exe_dir}/imgui.ini",
    ]
    for file in files_to_clean_always:
        if os.path.isfile(file):
            os.remove(os.path.normpath(file))

    if not game_info.using_keep_mods_and_settings:
        ue4ss_dir = os.path.normpath(f"{exe_dir}/ue4ss")
        if os.path.isdir(ue4ss_dir):
            shutil.rmtree(ue4ss_dir)
        ue4ss_dir = os.path.normpath(f"{exe_dir}/Mods")
        if os.path.isdir(ue4ss_dir):
            shutil.rmtree(ue4ss_dir)

    delete_all_empty_dirs_in_dir_tree(game_info.install_dir)

    did_uninstall_work = True

    for file in files_to_clean_always:
        if os.path.isfile(file):
            did_uninstall_work = False
            break

    if did_uninstall_work:
        for file_to_delete in game_info.installed_files:
            file_to_delete_actual_path = os.path.normpath(f"{exe_dir}/{file_to_delete}")
            if os.path.isfile(file_to_delete_actual_path):
                did_uninstall_work = False
                break

    if did_uninstall_work:
        update_game_info_field_from_ui(user_data, "installed_files", [])
    else:
        push_uninstall_failed_screen(user_data=user_data)

    main_ue4ss_screen.refresh_game_list_scroll_box()


def install_ue4ss(user_data):
    exe_dir = get_exe_dir_from_game_dir(user_data)
    ue4ss_zip_path = pathlib.Path(f"{file_io.SCRIPT_DIR}/temp/ue4ss.zip")
    file_io.unzip_zip(ue4ss_zip_path, exe_dir)
    all_paths_in_zip = file_io.get_paths_of_files_in_zip(ue4ss_zip_path)
    install_was_successful = True
    for file in all_paths_in_zip:
        if not os.path.isfile(os.path.normpath(f"{exe_dir}/{file}")):
            install_was_successful = False
            break
    if not install_was_successful:
        push_install_failed_screen(user_data=user_data)
    update_game_info_field_from_ui(user_data, "installed_files", all_paths_in_zip)


def download_ue4ss(user_data):
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        user_data
    )
    if game_info:
        os.makedirs(str(file_io.get_temp_dir()), exist_ok=True)
        file_names_to_download_links = ue4ss.get_file_name_to_download_links_from_tag(
            game_info.ue4ss_version
        )
        download_link = file_names_to_download_links.get(
            game_info.last_installed_version
        )
        file_io.download_file(
            download_link,
            os.path.normpath(f"{str(file_io.get_temp_dir())}/ue4ss.zip"),
        )


def clean_up_temp_files(user_data):
    if isinstance(user_data, list):
        user_data = user_data[0]
    temp_dir = file_io.get_temp_dir()
    if os.path.isdir(temp_dir):
        shutil.rmtree(temp_dir)


def push_installing_from_zip_screen(sender, app_data, user_data):
    last_installed_file = ""  # have this use provided file later
    ue4ss_version = ""  # have this use provided file later
    update_game_info_field_from_ui(
        user_data, "last_installed_version", last_installed_file
    )
    update_game_info_field_from_ui(user_data, "ue4ss_version", ue4ss_version)
    screen_tag = "installing_ue4ss_from_zip_modal"
    if dpg.does_item_exist(screen_tag):
        dpg.delete_item(screen_tag)
    game_directory = user_data
    zip_file = app_data["file_path_name"]
    user_data = [game_directory, zip_file]
    setup_screen.push_setup_screen(
        tag=screen_tag,
        task_text=translator.translator.translate(
            "installing_from_zip_ue4ss_task_text"
        ),
        finished_all_steps_function=push_install_successful_screen,
        user_data=user_data,
        step_text_to_step_functions={
            translator.translator.translate(
                "uninstalling_old_ue4ss_files_step_text"
            ): uninstall_ue4ss,
            translator.translator.translate(
                "installing_ue4ss_step_text"
            ): install_ue4ss_through_zip,
            translator.translator.translate(
                "cleaning_up_temp_files_step_text"
            ): clean_up_temp_files,
        },
    )


def push_installing_from_zip_screen_file_selection(sender, app_data, user_data):
    if dpg.does_item_exist("zip_picker"):
        dpg.delete_item("zip_picker")

    dpg.add_file_dialog(
        directory_selector=False,
        show=True,
        callback=push_installing_from_zip_screen,
        tag="zip_picker",
        width=constants.WINDOW_WIDTH - 80,
        height=constants.WINDOW_HEIGHT - 80,
        modal=True,
        file_count=999,
        user_data=user_data,
    )
    dpg.add_file_extension(parent="zip_picker", extension=".zip")
    dpg.add_file_extension(parent="zip_picker", extension=".rar")
    dpg.add_file_extension(parent="zip_picker", extension=".7z")


def push_installing_screen(sender, app_data, user_data):
    last_installed_file = dpg.get_value("ue4ss_file_to_install_combo_box")
    if last_installed_file is None or last_installed_file == "":
        return
    ue4ss_version = dpg.get_value("tags_combo_box")
    update_game_info_field_from_ui(
        user_data, "last_installed_version", last_installed_file
    )
    update_game_info_field_from_ui(user_data, "ue4ss_version", ue4ss_version)
    screen_tag = "installing_ue4ss_modal"
    if dpg.does_item_exist(screen_tag):
        dpg.delete_item(screen_tag)
    setup_screen.push_setup_screen(
        tag=screen_tag,
        task_text=translator.translator.translate("installing_ue4ss_task_text"),
        finished_all_steps_function=push_install_successful_screen,
        user_data=user_data,
        step_text_to_step_functions={
            translator.translator.translate(
                "uninstalling_old_ue4ss_files_step_text"
            ): uninstall_ue4ss,
            translator.translator.translate(
                "downloading_ue4ss_zip_step_text"
            ): download_ue4ss,
            translator.translator.translate(
                "installing_ue4ss_step_text"
            ): install_ue4ss,
            translator.translator.translate(
                "cleaning_up_temp_files_step_text"
            ): clean_up_temp_files,
        },
    )


def push_reinstalling_screen(sender, app_data, user_data):
    last_installed_file = dpg.get_value("ue4ss_file_to_install_combo_box")
    ue4ss_version = dpg.get_value("tags_combo_box")
    update_game_info_field_from_ui(
        user_data, "last_installed_version", last_installed_file
    )
    update_game_info_field_from_ui(user_data, "ue4ss_version", ue4ss_version)
    screen_tag = "reinstalling_ue4ss_modal"
    if dpg.does_item_exist(screen_tag):
        dpg.delete_item(screen_tag)
    setup_screen.push_setup_screen(
        tag=screen_tag,
        task_text=translator.translator.translate("reinstalling_ue4ss_task_text"),
        finished_all_steps_function=push_install_successful_screen,
        user_data=user_data,
        step_text_to_step_functions={
            translator.translator.translate(
                "uninstalling_old_ue4ss_files_step_text"
            ): uninstall_ue4ss,
            translator.translator.translate(
                "downloading_ue4ss_zip_step_text"
            ): download_ue4ss,
            translator.translator.translate(
                "installing_ue4ss_step_text"
            ): install_ue4ss,
            translator.translator.translate(
                "cleaning_up_temp_files_step_text"
            ): clean_up_temp_files,
        },
    )


def push_uninstalling_screen(sender, app_data, user_data):
    screen_tag = "uninstalling_ue4ss_modal"
    if dpg.does_item_exist(screen_tag):
        dpg.delete_item(screen_tag)
    setup_screen.push_setup_screen(
        tag=screen_tag,
        task_text=translator.translator.translate("uninstalling_ue4ss_task_text"),
        finished_all_steps_function=push_uninstall_successful_screen,
        user_data=user_data,
        step_text_to_step_functions={
            translator.translator.translate(
                "uninstalling_old_ue4ss_files_step_text"
            ): uninstall_ue4ss
        },
    )


def dismiss_configure_game_modal():
    dpg.delete_item("configure_game_modal")


def push_configure_game_screen(sender, app_data, user_data):
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        str(user_data)
    )
    if online_check.is_online:
        pos_y = 120
    else:
        pos_y = 260
    if game_info:
        if dpg.does_item_exist("configure_game_modal"):
            dpg.delete_item("configure_game_modal")
        dpg.add_window(
            modal=True,
            tag="configure_game_modal",
            no_title_bar=True,
            min_size=[524, 1],
            max_size=[524, 999],
            autosize=True,
            no_open_over_existing_popup=False,
            pos=[30, pos_y],
            no_move=True,
            no_resize=True,
        )

        install_dir = str(game_info.install_dir)
        matched = False

        centered_game_name_text = "default centered game name text"

        for game_key in constants.GAME_PATHS_TO_DISPLAY_NAMES.keys():
            if game_key in install_dir:
                centered_game_name_text = (
                    f"Game: {str(constants.GAME_PATHS_TO_DISPLAY_NAMES[game_key])}"
                )
                matched = True
                break

        if not matched:
            centered_game_name_text = f"Game: {game_info.game_title}"

        auto_align.add_multi_line_centered_text(centered_game_name_text, parent="configure_game_modal")

        dpg.add_spacer(parent="configure_game_modal")

        auto_align.add_multi_line_centered_text(
            f"{translator.translator.translate('game_directory_text_label')} {str(game_info.install_dir)}",
            parent="configure_game_modal",
        )

        dpg.add_spacer(parent="configure_game_modal")

        if online_check.is_online:
            auto_align.add_centered_text(
                translator.translator.translate("ue4ss_version_text_label"),
                parent="configure_game_modal",
            )

            dpg.add_spacer(parent="configure_game_modal")

            if game_info.show_pre_releases:
                combo_items = ue4ss.get_all_tags_with_assets()
            else:
                combo_items = ue4ss.get_normal_release_tags_with_assets()
            if game_info.ue4ss_version in combo_items:
                default_combo_item = game_info.ue4ss_version
            else:
                default_combo_item = combo_items[0]

            dpg.add_input_text(
                width=-1,
                hint=translator.translator.translate("filter_ue4ss_version_hint"),
                parent="configure_game_modal",
                tag="filter_ue4ss_tag",
                callback=filter_ue4ss_tag,
                user_data=user_data,
            )

            dpg.add_combo(
                tag="tags_combo_box",
                items=combo_items,
                default_value=default_combo_item,
                callback=on_ue4ss_version_tag_combo_box_selected,
                user_data=user_data,
                width=-1,
                parent="configure_game_modal",
            )

            dpg.add_spacer(parent="configure_game_modal")

            auto_align.add_centered_text(
                translator.translator.translate("ue4ss_file_to_install_text_label"),
                parent="configure_game_modal",
            )

            dpg.add_spacer(parent="configure_game_modal")

            dpg.add_input_text(
                hint=translator.translator.translate("filter_ue4ss_file_hint"),
                parent="configure_game_modal",
                width=-1,
                tag="filter_ue4ss_file_to_install",
                callback=filter_ue4ss_file_to_install,
                user_data=user_data,
            )

            dpg.add_combo(
                tag="ue4ss_file_to_install_combo_box",
                items=[],
                default_value="",
                user_data=user_data,
                width=-1,
                parent="configure_game_modal",
            )

            refresh_file_to_install_combo_box(user_data)

            dpg.add_spacer(parent="configure_game_modal", height=4)
            with dpg.group(horizontal=True, parent="configure_game_modal"):
                dpg.add_checkbox(
                    default_value=game_info.show_pre_releases,
                    tag="pre_releases_check_box",
                    callback=on_using_pre_releases_check_box_toggled,
                    user_data=user_data,
                )
                dpg.add_text(
                    translator.translator.translate("enable_pre_releases_text_label")
                )

            dpg.add_spacer(parent="configure_game_modal")
            with dpg.group(horizontal=True, parent="configure_game_modal"):
                dpg.add_checkbox(
                    default_value=game_info.using_developer_version,
                    tag="developer_version_check_box",
                    callback=on_developer_check_box_toggled,
                    user_data=user_data,
                )
                dpg.add_text(
                    translator.translator.translate(
                        "install_developer_version_text_label"
                    )
                )

            dpg.add_spacer(parent="configure_game_modal")
            with dpg.group(horizontal=True, parent="configure_game_modal"):
                dpg.add_checkbox(
                    default_value=game_info.using_portable_version,
                    tag="portable_version_check_box",
                    callback=on_portable_version_check_box_toggled,
                    user_data=user_data,
                )
                dpg.add_text(
                    translator.translator.translate(
                        "install_portable_version_text_label"
                    )
                )

            dpg.add_spacer(parent="configure_game_modal")
            with dpg.group(horizontal=True, parent="configure_game_modal"):
                dpg.add_checkbox(
                    default_value=game_info.using_keep_mods_and_settings,
                    tag="keep_mods_and_settings_check_box",
                    callback=on_keep_mods_and_settings_check_box_toggled,
                    user_data=user_data,
                )
                dpg.add_text(
                    translator.translator.translate("keep_mods_and_settings_text_label")
                )

            dpg.add_spacer(parent="configure_game_modal")


        is_installed = get_should_show_uninstall_button(user_data)
        online_and_installed_buttons: dict[str, dict[Callable[..., Any], dict[str, Any]]] = {
            "uninstall_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("uninstall_button_text"),
                    "height": 28,
                    "width": -1,
                    "callback": push_uninstalling_screen,
                    "user_data": pathlib.Path(user_data),
                    "show": is_installed,
                }
            },
            "reinstall_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("reinstall_button_text"),
                    "height": 28,
                    "width": -1,
                    "callback": push_reinstalling_screen,
                    "user_data": pathlib.Path(user_data),
                    "show": is_installed,
                }
            }
        }


        online_and_not_installed_buttons: dict[str, dict[Callable[..., Any], dict[str, Any]]] = {
            "install_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("install_button_text"),
                    "height": 28,
                    "width": -1,
                    "callback": push_installing_screen,
                    "user_data": pathlib.Path(user_data),
                    "show": not is_installed,
                }
            },
            "install_from_zip_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("install_from_zip_button_text"),
                    "height": 28,
                    "width": -1,
                    "callback": push_installing_from_zip_screen_file_selection,
                    "user_data": pathlib.Path(user_data),
                    "show": not is_installed,
                }
            }
        }


        offline_and_installed_buttons: dict[str, dict[Callable[..., Any], dict[str, Any]]] = {
            "uninstall_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("uninstall_button_text"),
                    "height": 28,
                    "width": -1,
                    "callback": push_uninstalling_screen,
                    "user_data": pathlib.Path(user_data),
                    "show": is_installed,
                }
            }
        }


        offline_and_not_installed_buttons: dict[str, dict[Callable[..., Any], dict[str, Any]]] = {
            "install_from_zip_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("install_from_zip_button_text"),
                    "height": 28,
                    "width": -1,
                    "callback": push_installing_from_zip_screen_file_selection,
                    "user_data": pathlib.Path(user_data),
                    "show": not is_installed,
                }
            }
        }

        is_online = online_check.is_online

        if is_online and is_installed:
            button_set_one = online_and_installed_buttons
        elif is_online and not is_installed:
            button_set_one = online_and_not_installed_buttons
        elif not is_online and is_installed:
            button_set_one = offline_and_installed_buttons
        else:
            # not is_online and not is_installed
            button_set_one = offline_and_not_installed_buttons
        

        button_set_two: dict[str, dict[Callable[..., Any], dict[str, Any]]] = {
            "open_exe_dir_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("open_game_exe_directory"),
                    "width": -1,
                    "height": 28,
                    "callback": open_game_exe_dir,
                    "user_data": str(game_info.install_dir),
                }
            },
            "open_paks_dir_button": {
                dpg.add_button: {
                    "label": translator.translator.translate("open_game_paks_directory"),
                    "width": -1,
                    "height": 28,
                    "callback": open_game_paks_dir,
                    "user_data": str(game_info.install_dir),
                }
            },
            # "configure_lua_cpp_mods_button": {
            #     dpg.add_button: {
            #         "label": translator.translator.translate("configure_lua_cpp_mods"),
            #         "width": -1,
            #         "height": 28,
            #         "callback": ue4ss_mods_configurator.push_ue4ss_mods_configurator_screen,
            #         "user_data": str(game_info.install_dir),
            #     }
            # },
            # "configure_ue4ss_settings_button": {
            #     dpg.add_button: {
            #         "label": translator.translator.translate("configure_ue4ss_settings"),
            #         "width": -1,
            #         "height": 28,
            #         "callback": ue4ss_settings_configurator.push_screen,
            #         "user_data": str(game_info.install_dir),
            #     }
            # },
            # "configure_bp_mods_button": {
            #     dpg.add_button: {
            #         "label": translator.translator.translate("configure_ue4ss_bp_mods"),
            #         "width": -1,
            #         "height": 28,
            #         "callback": bp_mod_loader_configurator.push_bp_mod_loader_configuration_screen,
            #         "user_data": str(game_info.install_dir),
            #     }
            # },
            # "developer_utilities_button": {
            #     dpg.add_button: {
            #         "label": translator.translator.translate("developer_utilities"),
            #         "width": -1,
            #         "height": 28,
            #         "callback": developer_screen.push_developer_screen,
            #         "user_data": str(game_info.install_dir),
            #     }
            # },
        }

        grid.add_spaced_item_grid(
            parent_tag="configure_game_modal",
            callbacks_with_kwargs=button_set_one | button_set_two,
            column_row_preference=grid.ColumnRowPreference.Row,
            max_columns=2
        )


        dpg.add_button(
            label=translator.translator.translate("close_button_text"),
            parent="configure_game_modal",
            width=-1,
            height=28,
            callback=dismiss_configure_game_modal,
        )


def open_game_exe_dir(sender, app_data, game_directory: pathlib.Path):
    exe_dir = get_exe_dir_from_game_dir(pathlib.Path(game_directory))
    if settings.is_windows():
        os.startfile(exe_dir)
    else:
        subprocess.run(["xdg-open", exe_dir])


def get_should_show_uninstall_button(game_directory: pathlib.Path) -> bool:
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        str(game_directory)
    )
    if game_info:
        if len(game_info.installed_files) > 0:
            return True
        else:
            return False
    no_game_info_error = (
        "No game info, when get should show uninstall button was pressed."
    )
    raise RuntimeError(no_game_info_error)


def refresh_ue4ss_tags_combo_box(user_data):
    filter = dpg.get_value("filter_ue4ss_tag")
    game_info = settings.get_game_info_instance_in_settings_from_game_directory(
        user_data
    )

    if not game_info:
        return

    if game_info.show_pre_releases:
        all_tags = ue4ss.get_all_tags_with_assets()
    else:
        all_tags = ue4ss.get_normal_release_tags_with_assets()

    filtered_tags = [tag for tag in all_tags if filter.lower() in tag.lower()]

    dpg.configure_item("tags_combo_box", items=filtered_tags)

    if filtered_tags:
        if game_info.ue4ss_version in filtered_tags:
            dpg.set_value("tags_combo_box", game_info.ue4ss_version)
        else:
            dpg.set_value("tags_combo_box", filtered_tags[0])
    else:
        if all_tags:
            dpg.set_value("tags_combo_box", all_tags[0])
        else:
            dpg.set_value("tags_combo_box", "")


def get_exe_dir_from_game_dir(game_directory: pathlib.Path) -> pathlib.Path:
    engine_dir = game_directory / "Engine"

    for subdir in game_directory.rglob("*"):
        if subdir.is_dir():
            if engine_dir in subdir.parents:
                continue

            if subdir.name == "Win64" or subdir.name == "WinGDK":
                return subdir

    return pathlib.Path("")


def open_game_paks_dir(sender, app_data, game_directory: pathlib.Path):
    exe_dir = str(get_exe_dir_from_game_dir(pathlib.Path(game_directory)))
    game_dir = os.path.normpath(os.path.dirname(os.path.dirname(exe_dir)))
    content_dir = os.path.normpath(f"{game_dir}/Content")
    paks_dir = os.path.normpath(f"{content_dir}/Paks")
    if not os.path.isdir(paks_dir):
        if os.path.isdir(content_dir):
            dir_to_open = content_dir
        else:
            return
    else:
        dir_to_open = paks_dir
    if settings.is_windows():
        subprocess.run(["explorer", dir_to_open], check=False)
    else:
        subprocess.run(["xdg-open", dir_to_open])


def configure_mods():
    return


def configure_ue4ss_settings():
    return
