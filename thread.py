import threading
import time

def do_work(id, speed):
    while True:
        print("speed {} ".format(speed()))
        if speed() == 0:
            print("  Exiting loop.")
            break

def main():
    speed = 1

    tmp = threading.Thread(target=do_work, args=(id, lambda: speed))
    tmp.start()

    time.sleep(1)
    speed = .5

    time.sleep(1)

    print('stop motor')
    speed = 0

    tmp.join()

if __name__ == '__main__':
    main()