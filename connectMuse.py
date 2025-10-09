from brainflow.board_shim import BoardShim, BrainFlowInputParams, BoardIds

params = BrainFlowInputParams()

# If using native BLE support:
board_id = BoardIds.MUSE_2_BOARD

# If using BLED112 (older schema), you might do:
# board_id = BoardIds.MUSE_2_BLED_BOARD
# params.serial_port = "/dev/ttyUSB0"  # or whatever device for dongle

board = BoardShim(board_id, params)
board.prepare_session()
board.start_stream()
data = board.get_board_data()

# process data...
board.stop_stream()
board.release_session()


#muse 8073
#my ip 172.22.111.46
