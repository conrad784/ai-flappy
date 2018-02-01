#!/usr/bin/env python3
from itertools import cycle
import random
import sys
import numpy as np
from copy import deepcopy
from operator import itemgetter

import pygame
from pygame.locals import QUIT, KEYDOWN, K_ESCAPE, K_SPACE, K_UP

FPS = 30
SCREENWIDTH  = 288
SCREENHEIGHT = 512
# amount by which base can maximum shift to left
PIPEGAPSIZE  = 100 # gap between upper and lower part of pipe
BASEY        = SCREENHEIGHT * 0.79
# image, sound and hitmask  dicts
IMAGES, SOUNDS, HITMASKS = {}, {}, {}
FRAME_SKIP = 2
AGENT_FREQ = FRAME_SKIP
ENABLE_ROT = False
NUM_PATHS_VISIBLE = 4
SHOW_OTHER_PATHS = True

PLAYER_X = int(SCREENWIDTH * 0.2)
PIPE_VEL_X = -4

# player velocity, max velocity, downward accleration, accleration on flap
PLAYER_ROT_DEFAULT = 45
PLAYER_VEL_Y_DEFAULT = -9
PLAYER_VEL_Y = PLAYER_VEL_Y_DEFAULT  # player's velocity along Y, default same as playerFlapped
PLAYER_ROT = PLAYER_ROT_DEFAULT   # player's rotation
PLAYER_MAX_VEL_Y =  10   # max vel along Y, max descend speed
PLAYER_MIN_VEL_Y =  -8   # min vel along Y, max ascend speed TODO: implement?
PLAYER_ACC_Y    =   1   # players downward accleration
PLAYER_VEL_ROT  =   3   # angular speed
PLAYER_ROT_THR  =  20   # rotation threshold
PLAYER_FLAP_ACC =  -9   # players speed on flapping
SCORE_DISTR_VARIANCE = PIPEGAPSIZE/4 - 10
MAX_VISIBLE_DEPTH = (SCREENWIDTH - PLAYER_X) / abs(PIPE_VEL_X) / FRAME_SKIP

MAX_DESIRED_DEPTH = 13
MAX_DEPTH = min(MAX_DESIRED_DEPTH, MAX_VISIBLE_DEPTH)
MAX_PATHS = 20

# list of all possible players (tuple of 3 positions of flap)
PLAYERS_LIST = (
    # red bird
    (
        'assets/sprites/redbird-upflap.png',
        'assets/sprites/redbird-midflap.png',
        'assets/sprites/redbird-downflap.png',
    ),
    # blue bird
    (
        # amount by which base can maximum shift to left
        'assets/sprites/bluebird-upflap.png',
        'assets/sprites/bluebird-midflap.png',
        'assets/sprites/bluebird-downflap.png',
    ),
    # yellow bird
    (
        'assets/sprites/yellowbird-upflap.png',
        'assets/sprites/yellowbird-midflap.png',
        'assets/sprites/yellowbird-downflap.png',
    ),
)

# list of backgrounds
BACKGROUNDS_LIST = (
    'assets/sprites/background-day.png',
    'assets/sprites/background-night.png',
)

# list of pipes
PIPES_LIST = (
    'assets/sprites/pipe-green.png',
    'assets/sprites/pipe-red.png',
)

def main():
    global SCREEN, FPSCLOCK
    pygame.init()
    FPSCLOCK = pygame.time.Clock()
    SCREEN = pygame.display.set_mode((SCREENWIDTH, SCREENHEIGHT))
    pygame.display.set_caption('Flappy Bird')

    # numbers sprites for score display
    IMAGES['numbers'] = (
        pygame.image.load('assets/sprites/0.png').convert_alpha(),
        pygame.image.load('assets/sprites/1.png').convert_alpha(),
        pygame.image.load('assets/sprites/2.png').convert_alpha(),
        pygame.image.load('assets/sprites/3.png').convert_alpha(),
        pygame.image.load('assets/sprites/4.png').convert_alpha(),
        pygame.image.load('assets/sprites/5.png').convert_alpha(),
        pygame.image.load('assets/sprites/6.png').convert_alpha(),
        pygame.image.load('assets/sprites/7.png').convert_alpha(),
        pygame.image.load('assets/sprites/8.png').convert_alpha(),
        pygame.image.load('assets/sprites/9.png').convert_alpha()
    )

    # game over sprite
    IMAGES['gameover'] = pygame.image.load('assets/sprites/gameover.png').convert_alpha()
    # message sprite for welcome screen
    IMAGES['message'] = pygame.image.load('assets/sprites/message.png').convert_alpha()
    # base (ground) sprite
    IMAGES['base'] = pygame.image.load('assets/sprites/base.png').convert_alpha()

    # sounds
    if 'win' in sys.platform:
        soundExt = '.wav'
    else:
        soundExt = '.ogg'

    SOUNDS['die']    = pygame.mixer.Sound('assets/audio/die' + soundExt)
    SOUNDS['hit']    = pygame.mixer.Sound('assets/audio/hit' + soundExt)
    SOUNDS['point']  = pygame.mixer.Sound('assets/audio/point' + soundExt)
    SOUNDS['swoosh'] = pygame.mixer.Sound('assets/audio/swoosh' + soundExt)
    SOUNDS['wing']   = pygame.mixer.Sound('assets/audio/wing' + soundExt)

    # iterates over multiple games
    while True:
        # select random background sprites
        randBg = random.randint(0, len(BACKGROUNDS_LIST) - 1)
        IMAGES['background'] = pygame.image.load(BACKGROUNDS_LIST[randBg]).convert()

        # select random player sprites
        randPlayer = random.randint(0, len(PLAYERS_LIST) - 1)
        IMAGES['player'] = (
            pygame.image.load(PLAYERS_LIST[randPlayer][0]).convert_alpha(),
            pygame.image.load(PLAYERS_LIST[randPlayer][1]).convert_alpha(),
            pygame.image.load(PLAYERS_LIST[randPlayer][2]).convert_alpha(),
        )

        # select random pipe sprites
        pipeindex = random.randint(0, len(PIPES_LIST) - 1)
        IMAGES['pipe'] = (
            pygame.transform.rotate(
                pygame.image.load(PIPES_LIST[pipeindex]).convert_alpha(), 180),
            pygame.image.load(PIPES_LIST[pipeindex]).convert_alpha(),
        )

        # hismask for pipes
        HITMASKS['pipe'] = (
            getHitmask(IMAGES['pipe'][0]),
            getHitmask(IMAGES['pipe'][1]),
        )

        # hitmask for player
        HITMASKS['player'] = (
            getHitmask(IMAGES['player'][0]),
            getHitmask(IMAGES['player'][1]),
            getHitmask(IMAGES['player'][2]),
        )

        movementInfo = showWelcomeAnimation()
        crashInfo = mainGame(movementInfo)
        showGameOverScreen(crashInfo)


def showWelcomeAnimation():
    """Shows welcome screen animation of flappy bird"""
    global PLAYER_X
    # index of player to blit on screen
    playerIndex = 0
    playerIndexGen = cycle([0, 1, 2, 1])
    # iterator used to change playerIndex after every 5th iteration
    loopIter = 0

    playery = int((SCREENHEIGHT - IMAGES['player'][0].get_height()) / 2)

    messagex = int((SCREENWIDTH - IMAGES['message'].get_width()) / 2)
    messagey = int(SCREENHEIGHT * 0.12)

    basex = 0
    # amount by which base can maximum shift to left
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # player shm for up-down motion on welcome screen
    playerShmVals = {'val': 0, 'dir': 1}

    while True:
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP):
                # make first flap sound and return values for mainGame
                SOUNDS['wing'].play()
                return {
                    'playery': playery + playerShmVals['val'],
                    'basex': basex,
                    'playerIndexGen': playerIndexGen,
                }

        # adjust playery, playerIndex, basex
        if (loopIter + 1) % 5 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 4) % baseShift)
        playerShm(playerShmVals)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))
        SCREEN.blit(IMAGES['player'][playerIndex],
                    (PLAYER_X, playery + playerShmVals['val']))
        SCREEN.blit(IMAGES['message'], (messagex, messagey))
        SCREEN.blit(IMAGES['base'], (basex, BASEY))

        pygame.display.update()
        FPSCLOCK.tick(FPS)

def mainGame(movementInfo):
    global PLAYER_X
    global PIPE_VEL_X
    global PLAYER_VEL_Y
    global PLAYER_MAX_VEL_Y
    global PLAYER_MIN_VEL_Y
    global PLAYER_ACC_Y
    global PLAYER_ROT
    global PLAYER_VEL_ROT
    global PLAYER_ROT_THR
    global PLAYER_FLAP_ACC

    score = playerIndex = loopIter = 0
    playerIndexGen = movementInfo['playerIndexGen']
    playery = movementInfo['playery']

    basex = movementInfo['basex']
    baseShift = IMAGES['base'].get_width() - IMAGES['background'].get_width()

    # get 2 new pipes to add to upperPipes lowerPipes list
    newPipe1 = getRandomPipe()
    newPipe2 = getRandomPipe()

    # list of upper pipes
    upperPipes = [
        {'x': SCREENWIDTH + 200, 'y': newPipe1[0]['y']},
        {'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': newPipe2[0]['y']},
    ]

    # list of lowerpipe
    lowerPipes = [
        {'x': SCREENWIDTH + 200, 'y': newPipe1[1]['y']},
        {'x': SCREENWIDTH + 200 + (SCREENWIDTH / 2), 'y': newPipe2[1]['y']},
    ]

    playerFlapped = False # True when player flaps
    frame_count = 0
    path_frame_start = 0
    player_vel_y = PLAYER_VEL_Y
    player_rot = PLAYER_ROT

    while True:
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP):
                if playery > -2 * IMAGES['player'][0].get_height():
                    player_vel_y = PLAYER_FLAP_ACC
                    playerFlapped = True
                    SOUNDS['wing'].play()

        if playery > -2 * IMAGES['player'][0].get_height():
            if not frame_count % AGENT_FREQ:
                agent = Agent()
                flap, optimal_path = agent.findBestDecision(GameState(playery, player_vel_y, upperPipes, lowerPipes))
                path_frame_start = frame_count

                if flap:
                    player_vel_y = PLAYER_FLAP_ACC
                    playerFlapped = True
                    SOUNDS['wing'].play()
                    flap = False

        # check for crash here
        crashTest = checkCrash({'x': PLAYER_X, 'y': playery, 'index': playerIndex},
                               upperPipes, lowerPipes)
        if crashTest[0]:
            return {
                'y': playery,
                'groundCrash': crashTest[1],
                'basex': basex,
                'upperPipes': upperPipes,
                'lowerPipes': lowerPipes,
                'score': score,
                'player_vel_y': player_vel_y,
                'player_rot': player_rot
            }

        # check for score
        playerMidPos = PLAYER_X + IMAGES['player'][0].get_width() / 2
        for pipe in upperPipes:
            pipeMidPos = pipe['x'] + IMAGES['pipe'][0].get_width() / 2
            if pipeMidPos <= playerMidPos < pipeMidPos + 4:
                score += 1
                SOUNDS['point'].play()

        # playerIndex basex change
        if (loopIter + 1) % 3 == 0:
            playerIndex = next(playerIndexGen)
        loopIter = (loopIter + 1) % 30
        basex = -((-basex + 100) % baseShift)

        # rotate the player
        if player_rot > -90 and ENABLE_ROT:
            player_rot -= PLAYER_VEL_ROT

        # player's movement
        if player_vel_y < PLAYER_MAX_VEL_Y and not playerFlapped:
            player_vel_y += PLAYER_ACC_Y
        if playerFlapped:
            playerFlapped = False

            # more rotation to cover the threshold (calculated in visible rotation)
            if ENABLE_ROT:
                player_rot = 45

        playerHeight = IMAGES['player'][playerIndex].get_height()
        playery += min(player_vel_y, BASEY - playery - playerHeight)

        # move pipes to left
        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            uPipe['x'] += PIPE_VEL_X
            lPipe['x'] += PIPE_VEL_X

        # add new pipe when first pipe is about to touch left of screen
        if 0 < upperPipes[0]['x'] < 5:
            newPipe = getRandomPipe()
            upperPipes.append(newPipe[0])
            lowerPipes.append(newPipe[1])

        # remove first pipe if its out of the screen
        if upperPipes[0]['x'] < -IMAGES['pipe'][0].get_width():
            upperPipes.pop(0)
            lowerPipes.pop(0)

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            SCREEN.blit(IMAGES['pipe'][0], (uPipe['x'], uPipe['y']))
            SCREEN.blit(IMAGES['pipe'][1], (lPipe['x'], lPipe['y']))

        SCREEN.blit(IMAGES['base'], (basex, BASEY))
        # print score so player overlaps the score
        showScore(score)

        # Player rotation has a threshold
        if ENABLE_ROT:
            visibleRot = PLAYER_ROT_THR
        else:
            visibleRot = 0
        if player_rot <= PLAYER_ROT_THR and ENABLE_ROT:
            visibleRot = player_rot

        playerSurface = pygame.transform.rotate(IMAGES['player'][playerIndex], visibleRot)
        SCREEN.blit(playerSurface, (PLAYER_X, playery))

        mid_x, mid_y = IMAGES['player'][0].get_width() / 2, IMAGES['player'][0].get_height() / 2

        offset_x = (frame_count - path_frame_start) * PIPE_VEL_X
        mid_x += offset_x

        try:
            _, best_path = optimal_path[0]
        except:
            best_path = []

        if SHOW_OTHER_PATHS:
            for _, path in optimal_path:
                previous_x = deepcopy(PLAYER_X)
                previous_y = deepcopy(playery)
                for y in path:
                    x = previous_x - PIPE_VEL_X * FRAME_SKIP
                    pygame.draw.line(SCREEN, (0, 0, 255), (previous_x + mid_x, previous_y + mid_y), (x + mid_x, y + mid_y), 2)

                    previous_x = x
                    previous_y = y

        previous_x = deepcopy(PLAYER_X)
        previous_y = deepcopy(playery)
        for y in best_path:
            x = previous_x - PIPE_VEL_X * FRAME_SKIP
            pygame.draw.line(SCREEN, (255, 0, 0), (previous_x + mid_x, previous_y + mid_y), (x + mid_x, y + mid_y), 2)

            previous_x = x
            previous_y = y

        frame_count += 1

        pygame.display.update()
        FPSCLOCK.tick(FPS)


def showGameOverScreen(crashInfo):
    """crashes the player down ans shows gameover image"""
    global PLAYER_X
    score = crashInfo['score']
    playery = crashInfo['y']
    playerHeight = IMAGES['player'][0].get_height()
    player_vel_y = crashInfo['player_vel_y']
    player_acc_y = 2
    player_rot = crashInfo['player_rot']
    player_vel_rot = 7

    basex = crashInfo['basex']

    upperPipes, lowerPipes = crashInfo['upperPipes'], crashInfo['lowerPipes']

    # play hit and die sounds
    SOUNDS['hit'].play()
    if not crashInfo['groundCrash']:
        SOUNDS['die'].play()

    while True:
        for event in pygame.event.get():
            if event.type == QUIT or (event.type == KEYDOWN and event.key == K_ESCAPE):
                pygame.quit()
                sys.exit()
            if event.type == KEYDOWN and (event.key == K_SPACE or event.key == K_UP):
                if playery + playerHeight >= BASEY - 1:
                    return

        # player y shift
        if playery + playerHeight < BASEY - 1:
            playery += min(player_vel_y, BASEY - playery - playerHeight)

        # player velocity change
        if player_vel_y < 15:
            player_vel_y += player_acc_y

        # rotate only when it's a pipe crash
        if not crashInfo['groundCrash']:
            if player_rot > -90:
                player_rot -= player_vel_rot

        # draw sprites
        SCREEN.blit(IMAGES['background'], (0,0))

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            SCREEN.blit(IMAGES['pipe'][0], (uPipe['x'], uPipe['y']))
            SCREEN.blit(IMAGES['pipe'][1], (lPipe['x'], lPipe['y']))

        SCREEN.blit(IMAGES['base'], (basex, BASEY))
        showScore(score)

        playerSurface = pygame.transform.rotate(IMAGES['player'][1], player_rot)
        SCREEN.blit(playerSurface, (PLAYER_X,playery))

        FPSCLOCK.tick(FPS)
        pygame.display.update()

def scoreFunction(displacement, cutoff=None):
    """
    Gives score given a displacement, currently gaussian distribution because I'm not creative

    arguments:
        displacement (float) - how far the player is away from the goal
        cutoff       (float) - at which displacement to award 0 points
    returns:
        score        (float) - score corresponding to this displacement
    """
    global SCORE_DISTR_VARIANCE
    global PIPEGAPSIZE
    if not cutoff:
        cutoff = PIPEGAPSIZE/2 - IMAGES['player'][0].get_height()/2
    return np.exp(-np.power(displacement, 2.)/(2*np.power(SCORE_DISTR_VARIANCE, 2.))) - np.exp(-np.power(cutoff, 2.)/(2*np.power(SCORE_DISTR_VARIANCE, 2.)))

class GameState():
    def __init__(self, _player_y, _player_vel_y, _upper_pipes, _lower_pipes):
        self.player_y = deepcopy(_player_y)
        self.player_vel_y = deepcopy(_player_vel_y)
        self.upper_pipes = deepcopy(_upper_pipes)
        self.lower_pipes = deepcopy(_lower_pipes)

    def next(self, flap):
        """
        This method advances the GameState by 1 tick and checks, whether or not the player crashes.
        arguments:
            flap (bool) whether or not the player flaps at the beginning of the tick
        return:
            True   -   crash
            False  -   no crash
        """
        global PLAYER_FLAP_ACC
        global PLAYER_ACC_Y
        global PLAYER_X
        global PIPE_VEL_X
        global BASEY

        flapped = False

        for _ in range(FRAME_SKIP):
            if self.player_y > -2 * IMAGES['player'][0].get_height() and flap: # check if out of image
                self.player_vel_y = PLAYER_FLAP_ACC
                flap = False
                flapped = True

            # check for crash here
            for index in range(3):
                crashTest = checkCrash({'x': PLAYER_X, 'y': self.player_y, 'index': index},
                                       self.upper_pipes, self.lower_pipes)

                if crashTest[0]:
                    return True

            # player's movement
            if self.player_vel_y < PLAYER_MAX_VEL_Y and not flapped: # max vel check for friction
                self.player_vel_y += PLAYER_ACC_Y
            flapped = False

            playerHeight = IMAGES['player'][0].get_height() # TODO: check if this causes crashes if we dont continue to rotate 0 -> playerIndex
            self.player_y += min(self.player_vel_y, BASEY - self.player_y - playerHeight)

            # move pipes to left
            for uPipe, lPipe in zip(self.upper_pipes, self.lower_pipes):
                uPipe['x'] += PIPE_VEL_X
                lPipe['x'] += PIPE_VEL_X

        # check for crash here
        for index in range(3):
            crashTest = checkCrash({'x': PLAYER_X, 'y': self.player_y, 'index': index},
                                   self.upper_pipes, self.lower_pipes)

            if crashTest[0]:
                return True
        return False

    def getScore(self):
        global PIPEGAPSIZE
        goal = SCREENHEIGHT / 2

        pipeW = IMAGES['pipe'][0].get_width()
        leftest_pipe_u = min(self.upper_pipes, key=lambda p: p['x'] if PLAYER_X < p['x'] + pipeW else np.inf)
        u_lower_bound = leftest_pipe_u['y'] + IMAGES['pipe'][0].get_height()

        if leftest_pipe_u['x'] < SCREENWIDTH:
            goal = u_lower_bound + PIPEGAPSIZE/2

        displacement = abs(goal - self.player_y)

        return scoreFunction(displacement)

class Agent():
    def getPathScore(self, state):
        global MAX_DEPTH
        global MAX_PATHS
        global NUM_PATHS_VISIBLE
        #      state, depth, score, list of choices
        stack = [(state, 0, 0, [state.player_y])]
        final_states = []
        max_num = MAX_PATHS
        while len(stack):
            state1, curr_depth, score, pos_hist1 = stack.pop()
            if curr_depth >= MAX_DEPTH:
                final_states.append((score, pos_hist1))
                max_num -= 1
                if not max_num:
                    break
                continue
            state2, pos_hist2 = deepcopy(state1), deepcopy(pos_hist1)

            if not state1.next(True):
                pos_hist1.append(state1.player_y)
                stack.append((state1, curr_depth+1, score+state1.getScore(), pos_hist1))
            if not state2.next(False):
                pos_hist2.append(state2.player_y)
                stack.append((state2, curr_depth+1, score+state2.getScore(), pos_hist2))

        final_states.sort(key=itemgetter(0))
        final_states = final_states[:NUM_PATHS_VISIBLE]

        try:
            highscore = final_states[0][0], final_states
        except IndexError:
            highscore = 0, []
        return highscore

    def findBestDecision(self, state):
        no_flap = deepcopy(state)

        if state.next(True):
            no_flap.next(False)
            score, path = self.getPathScore(no_flap)
            return False, path

        if no_flap.next(False):
            score, path = self.getPathScore(state)
            return True, path

        flap_score, flap_traj = self.getPathScore(state)
        no_flap_score, no_flap_traj = self.getPathScore(no_flap)

        if flap_score > no_flap_score:
            return True, flap_traj
        else:
            return False, no_flap_traj

def playerShm(playerShm):
    """oscillates the value of playerShm['val'] between 8 and -8"""
    if abs(playerShm['val']) == 8:
        playerShm['dir'] *= -1

    if playerShm['dir'] == 1:
         playerShm['val'] += 1
    else:
        playerShm['val'] -= 1


def getRandomPipe():
    """returns a randomly generated pipe"""
    # y of gap between upper and lower pipe
    gapY = random.randrange(0, int(BASEY * 0.6 - PIPEGAPSIZE))
    gapY += int(BASEY * 0.2)
    pipeHeight = IMAGES['pipe'][0].get_height()
    pipeX = SCREENWIDTH + 10

    return [
        {'x': pipeX, 'y': gapY - pipeHeight},  # upper pipe
        {'x': pipeX, 'y': gapY + PIPEGAPSIZE}, # lower pipe
    ]


def showScore(score):
    """displays score in center of screen"""
    scoreDigits = [int(x) for x in list(str(score))]
    totalWidth = 0 # total width of all numbers to be printed

    for digit in scoreDigits:
        totalWidth += IMAGES['numbers'][digit].get_width()

    Xoffset = (SCREENWIDTH - totalWidth) / 2

    for digit in scoreDigits:
        SCREEN.blit(IMAGES['numbers'][digit], (Xoffset, SCREENHEIGHT * 0.1))
        Xoffset += IMAGES['numbers'][digit].get_width()


def checkCrash(player, upperPipes, lowerPipes):
    """returns True if player collders with base or pipes."""
    pi = player['index']
    player['w'] = IMAGES['player'][0].get_width()
    player['h'] = IMAGES['player'][0].get_height()

    # if player crashes into ground
    if player['y'] + player['h'] >= BASEY - 1:
        return [True, True]
    else:

        playerRect = pygame.Rect(player['x'], player['y'],
                      player['w'], player['h'])
        pipeW = IMAGES['pipe'][0].get_width()
        pipeH = IMAGES['pipe'][0].get_height()

        for uPipe, lPipe in zip(upperPipes, lowerPipes):
            # upper and lower pipe rects
            uPipeRect = pygame.Rect(uPipe['x'], uPipe['y'], pipeW, pipeH)
            lPipeRect = pygame.Rect(lPipe['x'], lPipe['y'], pipeW, pipeH)

            # player and upper/lower pipe hitmasks
            pHitMask = HITMASKS['player'][pi]
            uHitmask = HITMASKS['pipe'][0]
            lHitmask = HITMASKS['pipe'][1]

            # if bird collided with upipe or lpipe
            uCollide = pixelCollision(playerRect, uPipeRect, pHitMask, uHitmask)
            lCollide = pixelCollision(playerRect, lPipeRect, pHitMask, lHitmask)

            if uCollide or lCollide:
                return [True, False]

    return [False, False]

def pixelCollision(rect1, rect2, hitmask1, hitmask2):
    """Checks if two objects collide and not just their rects"""
    rect = rect1.clip(rect2)

    if rect.width == 0 or rect.height == 0:
        return False

    x1, y1 = rect.x - rect1.x, rect.y - rect1.y
    x2, y2 = rect.x - rect2.x, rect.y - rect2.y

    for x in range(rect.width):
        for y in range(rect.height):
            if hitmask1[x1+x][y1+y] and hitmask2[x2+x][y2+y]:
                return True
    return False

def getHitmask(image):
    """returns a hitmask using an image's alpha."""
    mask = []
    for x in range(image.get_width()):
        mask.append([])
        for y in range(image.get_height()):
            mask[x].append(bool(image.get_at((x,y))[3]))
    return mask

if __name__ == '__main__':
    main()
