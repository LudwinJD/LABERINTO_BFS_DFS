import pygame
import sys
import random
import math
from collections import deque
import heapq

class Laberinto:
    def __init__(self, level):
        pygame.init()
        self.level = level
        self.screen = pygame.display.set_mode((1280, 720))
        pygame.display.set_caption(f"Laberinto - Nivel {level}")
        self.clock = pygame.time.Clock()
        self.running = True
        self.time_limit = 120
        self.start_time = pygame.time.get_ticks()

        self.block_size = 40
        self.load_assets()
        
        self.last_move_time = pygame.time.get_ticks()
        self.move_delay = 150

        # Variables para la IA y la resolucion del laberinto
        self.ai_solving = False
        self.ai_path = []
        self.ai_algorithm = None
        self.solving_steps = 0

        self.font = pygame.font.Font(None, 36)
        self.small_font = pygame.font.Font(None, 24)

        self.score = 0
        self.lives = 3
        
        # Inicializacion de listas importantes
        self.maze = []
        self.enemies = []
        self.original_enemies = []
        self.paths = []
        self.collectibles = []
        self.particles = []
        self.power_ups = []
        self.floating_texts = []

        self.load_map(f"maps/level{level}.txt")

        self.background = self.create_background()
        
        # Carga de sonidos
        pygame.mixer.music.load("assets/audio.mp3")
        pygame.mixer.music.play(-1)
        
        self.collect_sound = pygame.mixer.Sound("assets/coin.mp3")
        self.lose_life_sound = pygame.mixer.Sound("assets/death.mp3")

        self.invincible = False

    def load_assets(self):
        # Carga de imagenes y creacion de animaciones
        self.images = {name: pygame.transform.scale(pygame.image.load(f"assets/{name}.png"), (self.block_size, self.block_size))
                       for name in ['wall', 'enemy', 'goal', 'path', 'coin', 'power_up']}
        self.player_frames = [pygame.transform.scale(pygame.image.load(f"assets/player_{i}.png"), (self.block_size, self.block_size))
                              for i in range(4)]
        self.current_frame = 0
        self.animation_timer = 0

    def create_background(self):
        # Creacion de un fondo con estrellas
        background = pygame.Surface((1280, 720))
        for _ in range(100):
            x, y = random.randint(0, 1279), random.randint(0, 719)
            color = random.choice([(255, 255, 255), (200, 200, 200), (150, 150, 150)])
            pygame.draw.circle(background, color, (x, y), random.randint(1, 3))
        return background

    def load_map(self, filepath):
        # Carga del mapa desde un archivo
        self.maze = []
        self.enemies = []
        self.player = None
        self.goal = None
        self.paths = []

        with open(filepath, 'r') as file:
            for y, line in enumerate(file):
                for x, char in enumerate(line.strip()):
                    rect = pygame.Rect(x * self.block_size, y * self.block_size, self.block_size, self.block_size)
                    if char == '#':
                        self.maze.append(rect)
                    elif char == 'M':
                        self.enemies.append(rect)
                    elif char == 'P':
                        self.player = rect
                    elif char == 'E':
                        self.goal = rect
                    elif char == '.':
                        self.paths.append(rect)
                    elif char == 'C':
                        self.collectibles.append(rect)
                    elif char == 'U':
                        self.power_ups.append(rect)

        self.paths.extend([self.player.copy()] + [enemy.copy() for enemy in self.enemies])

    def run(self):
        # Bucle principal del juego
        self.show_instructions()
        last_enemy_move_time = pygame.time.get_ticks()
        while self.running:
            self.handle_events()
            self.update()
            current_time = pygame.time.get_ticks()
            if current_time - last_enemy_move_time > 500:
                self.move_enemies()
                last_enemy_move_time = current_time
            self.draw()
            self.clock.tick(60)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.quit_game()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    self.running = False
                elif event.key == pygame.K_r:
                    self.reset_level()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if self.ai_button_rect.collidepoint(event.pos):
                    self.toggle_ai_solving()
                elif self.dfs_button_rect.collidepoint(event.pos):
                    self.ai_algorithm = 'DFS'
                elif self.bfs_button_rect.collidepoint(event.pos):
                    self.ai_algorithm = 'BFS'
                elif self.greedy_button_rect.collidepoint(event.pos):
                    self.ai_algorithm = 'Greedy'
                elif self.astar_button_rect.collidepoint(event.pos):
                    self.ai_algorithm = 'A*'
            if event.type == pygame.USEREVENT:
                self.move_delay = 150  # Reset speed
            elif event.type == pygame.USEREVENT + 1:
                self.invincible = False

    def remove_enemies(self):
        # Eliminar enemigos temporalmente
        self.original_enemies = self.enemies.copy()
        self.enemies.clear()

    def restore_enemies(self):
        # Restaurar enemigos
        self.enemies = self.original_enemies.copy()

    def move_player_to(self, position):
        # Mover al jugador a una posicion especifica
        self.player.topleft = position
        self.check_collectibles()
        self.check_power_ups()
        self.create_movement_particles(self.player.center)

    def move_player(self, move_x, move_y):
        # Mover al jugador
        new_position = self.player.move(move_x, move_y)
        if not any(new_position.colliderect(wall) for wall in self.maze):
            self.move_player_to(new_position.topleft)

    def is_safe(self, pos):
        # Verificar si una posicion es segura
        return not any(enemy.collidepoint(pos) for enemy in self.enemies)
    
    def solve_maze_dfs(self):
        # Resolver el laberinto usando DFS (Depth-First Search)
        start = self.player.topleft
        goal = self.goal.topleft
        stack = [(start, [start])]
        visited = set()

        while stack:
            (current, path) = stack.pop()
            if current not in visited:
                visited.add(current)

                if current == goal:
                    return path

                for dx, dy in [(0, self.block_size), (self.block_size, 0), (0, -self.block_size), (-self.block_size, 0)]:
                    neighbor = (current[0] + dx, current[1] + dy)
                    if (not any(wall.collidepoint(neighbor) for wall in self.maze) and
                        self.is_safe(neighbor) and neighbor not in visited):
                        stack.append((neighbor, path + [neighbor]))

        return []  # No se encontro camino
    
    def solve_maze_bfs(self):
        # Resolver el laberinto usando BFS (Breadth-First Search)
        start = self.player.topleft
        goal = self.goal.topleft
        queue = deque([(start, [start])])
        visited = set()

        while queue:
            (current, path) = queue.popleft()
            if current not in visited:
                visited.add(current)

                if current == goal:
                    return path

                for dx, dy in [(0, self.block_size), (self.block_size, 0), (0, -self.block_size), (-self.block_size, 0)]:
                    neighbor = (current[0] + dx, current[1] + dy)
                    if (not any(wall.collidepoint(neighbor) for wall in self.maze) and
                        self.is_safe(neighbor) and neighbor not in visited):
                        queue.append((neighbor, path + [neighbor]))

        return []  # No se encontro camino

    def solve_maze_greedy(self):
        start = self.player.topleft
        goal = self.goal.topleft
        
        def heuristic(a, b):
            return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        
        visited = set()
        heap = [(heuristic(start, goal), start)]
        came_from = {start: None}
        
        while heap:
            _, current = heapq.heappop(heap)
            
            if current == goal:
                path = []
                while current:
                    path.append(current)
                    current = came_from[current]
                return path[::-1]
            
            if current in visited:
                continue
            
            visited.add(current)
            
            for dx, dy in [(0, self.block_size), (self.block_size, 0), (0, -self.block_size), (-self.block_size, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if (not any(wall.collidepoint(neighbor) for wall in self.maze) and
                    self.is_safe(neighbor) and neighbor not in visited):
                    came_from[neighbor] = current
                    heapq.heappush(heap, (heuristic(neighbor, goal), neighbor))
        
        return []  # No path found

    def solve_maze_astar(self):
        start = self.player.topleft
        goal = self.goal.topleft
        
        def heuristic(a, b):
            return math.sqrt((b[0] - a[0]) ** 2 + (b[1] - a[1]) ** 2)
        
        open_set = {start}
        came_from = {}
        g_score = {start: 0}
        f_score = {start: heuristic(start, goal)}
        
        while open_set:
            current = min(open_set, key=lambda pos: f_score[pos])
            
            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]
                path.append(start)
                return path[::-1]
            
            open_set.remove(current)
            
            for dx, dy in [(0, self.block_size), (self.block_size, 0), (0, -self.block_size), (-self.block_size, 0)]:
                neighbor = (current[0] + dx, current[1] + dy)
                if any(wall.collidepoint(neighbor) for wall in self.maze) or not self.is_safe(neighbor):
                    continue
                
                tentative_g_score = g_score[current] + self.block_size
                
                if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g_score
                    f_score[neighbor] = g_score[neighbor] + heuristic(neighbor, goal)
                    if neighbor not in open_set:
                        open_set.add(neighbor)
        
        return []  # No path found

    def toggle_ai_solving(self):
        self.ai_solving = not self.ai_solving
        if self.ai_solving and self.ai_algorithm:
            if self.ai_algorithm == 'DFS':
                self.ai_path = self.solve_maze_dfs()
            elif self.ai_algorithm == 'BFS':
                self.ai_path = self.solve_maze_bfs()
            elif self.ai_algorithm == 'Greedy':
                self.ai_path = self.solve_maze_greedy()
            elif self.ai_algorithm == 'A*':
                self.ai_path = self.solve_maze_astar()
            
            self.solving_steps = len(self.ai_path) - 1
            if not self.ai_path:
                print(f"No se encontró un camino seguro. La IA ({self.ai_algorithm}) no puede resolver el laberinto de forma segura.")
                self.ai_solving = False
            else:
                self.save_solution_image()
        else:
            self.restore_enemies()

    def save_solution_image(self):
        # Guardar imagen de la solucion
        maze_surface = pygame.Surface((self.screen.get_width(), self.screen.get_height()))
        maze_surface.fill((0, 0, 0))

        for wall in self.maze:
            pygame.draw.rect(maze_surface, (100, 100, 100), wall)
        
        for path in self.paths:
            pygame.draw.rect(maze_surface, (50, 50, 50), path)

        for i, pos in enumerate(self.ai_path):
            color = self.get_gradient_color(i, len(self.ai_path))
            pygame.draw.rect(maze_surface, color, (pos[0], pos[1], self.block_size, self.block_size))

        pygame.draw.rect(maze_surface, (0, 255, 0), self.player)
        pygame.draw.rect(maze_surface, (255, 0, 0), self.goal)

        steps_text = self.font.render(f"Pasos: {self.solving_steps}", True, (255, 255, 255))
        maze_surface.blit(steps_text, (10, 10))

        # Use a valid filename
        algorithm_name = self.ai_algorithm.replace('*', 'star')
        filename = f"solucion_laberinto_nivel{self.level}_{algorithm_name}.png"
        pygame.image.save(maze_surface, filename)

        # Crear y guardar el minimapa
        minimap_size = 400
        minimap_surface = pygame.Surface((minimap_size, minimap_size))
        minimap_surface.fill((0, 0, 0))

        scale_factor = minimap_size / max(self.screen.get_width(), self.screen.get_height())

        for wall in self.maze:
            pygame.draw.rect(minimap_surface, (100, 100, 100), 
                             (wall.x * scale_factor, wall.y * scale_factor, 
                              wall.width * scale_factor, wall.height * scale_factor))

        for i, pos in enumerate(self.ai_path):
            color = self.get_gradient_color(i, len(self.ai_path))
            pygame.draw.rect(minimap_surface, color, 
                             (pos[0] * scale_factor, pos[1] * scale_factor, 
                              self.block_size * scale_factor, self.block_size * scale_factor))

        pygame.draw.rect(minimap_surface, (0, 255, 0), 
                         (self.player.x * scale_factor, self.player.y * scale_factor, 
                          self.player.width * scale_factor, self.player.height * scale_factor))

        pygame.draw.rect(minimap_surface, (255, 0, 0), 
                         (self.goal.x * scale_factor, self.goal.y * scale_factor, 
                          self.goal.width * scale_factor, self.goal.height * scale_factor))

        steps_text = self.small_font.render(f"Pasos: {self.solving_steps}", True, (255, 255, 255))
        minimap_surface.blit(steps_text, (10, 10))

        # Use a valid filename for the minimap
        minimap_filename = f"minimapa_solucion_nivel{self.level}_{algorithm_name}.png"
        pygame.image.save(minimap_surface, minimap_filename)

    def get_gradient_color(self, step, total_steps):
        # Obtener color gradiente para la visualizacion de la solucion
        r = int(255 * (total_steps - step) / total_steps)
        g = int(255 * step / total_steps)
        b = 0
        return (r, g, b)

    def update(self):
        # Actualizar el estado del juego
        current_time = pygame.time.get_ticks()
        
        if self.ai_solving and self.ai_path:
            # Movimiento automatico si la IA esta resolviendo
            if current_time - self.last_move_time > self.move_delay:
                if self.ai_path:
                    next_pos = self.ai_path[0]
                    if self.is_safe(next_pos):
                        self.move_player_to(next_pos)
                        self.ai_path.pop(0)
                    else:
                        # Recalcular ruta si la posicion no es segura
                        self.ai_path = self.solve_maze_astar()
                        if not self.ai_path:
                            print("No se encontro un camino seguro. La IA no puede continuar.")
                            self.ai_solving = False
                self.last_move_time = current_time
        else:
            # Movimiento manual del jugador
            keys = pygame.key.get_pressed()
            move_x = keys[pygame.K_RIGHT] - keys[pygame.K_LEFT]
            move_y = keys[pygame.K_DOWN] - keys[pygame.K_UP]

            if (move_x != 0 or move_y != 0) and current_time - self.last_move_time > self.move_delay:
                self.move_player(move_x * self.block_size, move_y * self.block_size)
                self.last_move_time = current_time

        self.update_floating_texts()
        self.check_collectibles()
        self.check_power_ups()
        self.update_particles()

        # Verificar condiciones de victoria o derrota
        if self.player.colliderect(self.goal):
            self.show_win_screen()

        elapsed_time = (current_time - self.start_time) / 1000
        if elapsed_time > self.time_limit:
            self.show_lose_screen("Se acabo el tiempo")

        if not self.invincible:
            for enemy in self.enemies:
                if self.player.colliderect(enemy):
                    self.lose_life()

        self.update_player_animation()

    def move_enemies(self):
        # Mover enemigos aleatoriamente
        directions = [(self.block_size, 0), (-self.block_size, 0), (0, self.block_size), (0, -self.block_size)]
        new_positions = []
        for enemy in self.enemies:
            new_pos = enemy.move(random.choice(directions))
            if not any(new_pos.colliderect(wall) for wall in self.maze):
                new_positions.append(new_pos)
            else:
                new_positions.append(enemy.copy())

        # Evitar colisiones entre enemigos
        for i, new_pos in enumerate(new_positions):
            for j, other_pos in enumerate(new_positions):
                if i != j and new_pos.colliderect(other_pos):
                    new_positions[i] = self.enemies[i].copy()
                    break

        for i, new_position in enumerate(new_positions):
            self.paths.append(self.enemies[i].copy())
            self.enemies[i] = new_position

    def check_collectibles(self):
        # Verificar coleccion de monedas
        for collectible in self.collectibles[:]:
            if self.player.colliderect(collectible):
                self.collectibles.remove(collectible)
                self.paths.append(collectible)
                self.score += 10
                self.collect_sound.play()
                self.create_collect_particles(collectible.center)
                self.show_floating_text("+10", collectible.center, (255, 255, 0))

    def show_floating_text(self, text, position, color):
        # Mostrar texto flotante
        self.floating_texts.append({
            'text': self.small_font.render(text, True, color),
            'pos': list(position),
            'timer': 60
        })

    def update_floating_texts(self):
        # Actualizar posicion y duracion de textos flotantes
        for text in self.floating_texts[:]:
            text['pos'][1] -= 1
            text['timer'] -= 1
            if text['timer'] <= 0:
                self.floating_texts.remove(text)

    def check_power_ups(self):
        # Verificar coleccion de power-ups
        for power_up in self.power_ups[:]:
            if self.player.colliderect(power_up):
                self.power_ups.remove(power_up)
                self.paths.append(power_up)
                power_up_type = random.choice(['speed', 'invincibility', 'time'])
                self.activate_power_up(power_up_type)
                self.collect_sound.play()
                self.create_collect_particles(power_up.center)
    
    def activate_power_up(self, power_up_type):
        # Activar efecto del power-up
        if power_up_type == 'speed':
            self.move_delay = 75  # Movimiento mas rapido
            pygame.time.set_timer(pygame.USEREVENT, 10000)  # Duracion de 10 segundos
        elif power_up_type == 'invincibility':
            self.invincible = True
            pygame.time.set_timer(pygame.USEREVENT + 1, 5000)  # Duracion de 5 segundos
        elif power_up_type == 'time':
            self.time_limit += 30  # Agregar 30 segundos al tiempo limite

    def create_movement_particles(self, position):
        # Crear particulas de movimiento
        for _ in range(5):
            particle = {
                'pos': list(position),
                'vel': [random.uniform(-1, 1), random.uniform(-1, 1)],
                'timer': 20
            }
            self.particles.append(particle)

    def create_collect_particles(self, position):
        # Crear particulas al recoger items
        for _ in range(20):
            particle = {
                'pos': list(position),
                'vel': [random.uniform(-2, 2), random.uniform(-2, 2)],
                'timer': 30,
                'color': (255, 255, 0)
            }
            self.particles.append(particle)

    def update_particles(self):
        # Actualizar posicion y duracion de particulas
        for particle in self.particles[:]:
            particle['pos'][0] += particle['vel'][0]
            particle['pos'][1] += particle['vel'][1]
            particle['timer'] -= 1
            if particle['timer'] <= 0:
                self.particles.remove(particle)

    def update_player_animation(self):
        # Actualizar animacion del jugador
        self.animation_timer += 1
        if self.animation_timer >= 10:
            self.current_frame = (self.current_frame + 1) % len(self.player_frames)
            self.animation_timer = 0

    def draw(self):
        # Dibujar todos los elementos del juego
        self.screen.blit(self.background, (0, 0))
        for path in self.paths:
            self.screen.blit(self.images['path'], path)
        for wall in self.maze:
            self.screen.blit(self.images['wall'], wall)
        for enemy in self.enemies:
            self.screen.blit(self.images['enemy'], enemy)
        for collectible in self.collectibles:
            self.screen.blit(self.images['coin'], collectible)
            pulse = abs(math.sin(pygame.time.get_ticks() * 0.01)) * 5
            pygame.draw.circle(self.screen, (255, 255, 0, 100), collectible.center, self.block_size // 2 + pulse, 2)

        for power_up in self.power_ups:
            self.screen.blit(self.images['power_up'], power_up)
            glow = abs(math.sin(pygame.time.get_ticks() * 0.005)) * 10
            pygame.draw.circle(self.screen, (0, 255, 255, 50), power_up.center, self.block_size // 2 + glow, 3)
        self.screen.blit(self.player_frames[self.current_frame], self.player)
        self.screen.blit(self.images['goal'], self.screen.blit(self.images['goal'], self.goal))

        # Efectos visuales de power-ups activos
        if self.invincible:
            pygame.draw.circle(self.screen, (0, 255, 255, 100), self.player.center, self.block_size // 2 + 5, 2)
    
        if self.move_delay == 75:  # Power-up de velocidad activo
            pygame.draw.circle(self.screen, (255, 165, 0, 100), self.player.center, self.block_size // 2 + 3, 2)

        for text in self.floating_texts:
            self.screen.blit(text['text'], text['pos'])

        # Mostrar power-ups activos
        active_powerups = []
        if self.invincible:
            active_powerups.append("Invincible")
        if self.move_delay == 75:
            active_powerups.append("Speed")
        
        for i, powerup in enumerate(active_powerups):
            self.draw_text(powerup, (self.screen.get_width() - 150, 50 + i * 30), color=(255, 255, 0))
        
        # Dibujar particulas
        for particle in self.particles:
            color = particle.get('color', (255, 255, 255))
            pygame.draw.circle(self.screen, color, [int(p) for p in particle['pos']], 2)

        # Mostrar informacion del juego
        remaining_time = max(0, self.time_limit - (pygame.time.get_ticks() - self.start_time) / 1000)
        self.draw_text(f"Tiempo: {int(remaining_time)}s", (10, 10))
        self.draw_text(f"Nivel: {self.level}", (10, 50))
        self.draw_text(f"Puntuacion: {self.score}", (10, 90))
        self.draw_text(f"Vidas: {self.lives}", (10, 130))

        # Draw AI buttons
        self.ai_button_rect = pygame.Rect(900, 300, 160, 50)
        pygame.draw.rect(self.screen, (0, 255, 0) if self.ai_solving else (255, 0, 0), self.ai_button_rect)
        self.draw_text("IA: ON" if self.ai_solving else "IA: OFF", (self.ai_button_rect.x + 10, self.ai_button_rect.y + 10))

        self.dfs_button_rect = pygame.Rect(900, 360, 160, 50)
        self.bfs_button_rect = pygame.Rect(900, 420, 160, 50)
        self.greedy_button_rect = pygame.Rect(900, 480, 160, 50)
        self.astar_button_rect = pygame.Rect(900, 540, 160, 50)
        
        pygame.draw.rect(self.screen, (0, 200, 0) if self.ai_algorithm == 'DFS' else (200, 0, 0), self.dfs_button_rect)
        pygame.draw.rect(self.screen, (0, 200, 0) if self.ai_algorithm == 'BFS' else (200, 0, 0), self.bfs_button_rect)
        pygame.draw.rect(self.screen, (0, 200, 0) if self.ai_algorithm == 'Greedy' else (200, 0, 0), self.greedy_button_rect)
        pygame.draw.rect(self.screen, (0, 200, 0) if self.ai_algorithm == 'A*' else (200, 0, 0), self.astar_button_rect)
        
        self.draw_text("DFS", (self.dfs_button_rect.x + 10, self.dfs_button_rect.y + 10))
        self.draw_text("BFS", (self.bfs_button_rect.x + 10, self.bfs_button_rect.y + 10))
        self.draw_text("Greedy", (self.greedy_button_rect.x + 10, self.greedy_button_rect.y + 10))
        self.draw_text("A*", (self.astar_button_rect.x + 10, self.astar_button_rect.y + 10))

        # Show AI solution steps
        if self.ai_solving and self.solving_steps > 0:
            self.draw_text(f"Pasos: {self.solving_steps}", (900, 600), color=(255, 255, 0))

        self.draw_minimap()

        pygame.display.flip()

    def draw_text(self, text, pos, color=(255, 255, 255)):
        # Dibujar texto en la pantalla
        surface = self.font.render(text, True, color)
        self.screen.blit(surface, pos)

    def draw_minimap(self):
        # Dibujar minimapa
        minimap_size = 400
        minimap_surface = pygame.Surface((minimap_size, minimap_size))
        minimap_surface.set_alpha(128)
        minimap_surface.fill((0, 0, 0))

        scale_factor = minimap_size / max(self.screen.get_width(), self.screen.get_height())

        for wall in self.maze:
            pygame.draw.rect(minimap_surface, (100, 100, 100), 
                             (wall.x * scale_factor, wall.y * scale_factor, 
                              wall.width * scale_factor, wall.height * scale_factor))

        for enemy in self.enemies:
            pygame.draw.rect(minimap_surface, (255, 0, 0), 
                             (enemy.x * scale_factor, enemy.y * scale_factor, 
                              enemy.width * scale_factor, enemy.height * scale_factor))

        pygame.draw.rect(minimap_surface, (0, 255, 0), 
                         (self.player.x * scale_factor, self.player.y * scale_factor, 
                          self.player.width * scale_factor, self.player.height * scale_factor))

        pygame.draw.rect(minimap_surface, (0, 0, 255), 
                         (self.goal.x * scale_factor, self.goal.y * scale_factor, 
                          self.goal.width * scale_factor, self.goal.height * scale_factor))

        self.screen.blit(minimap_surface, (self.screen.get_width() - minimap_size - 10, 10))

    def show_instructions(self):
        # Mostrar pantalla de instrucciones
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        instructions = [
            "Laberinto - LJD",
            "-Usa las teclas de flecha para moverte",
            "-Recoge monedas para aumentar la puntuacion",
            "-Coge potenciadores para habilidades especiales",
            "-Evitar enemigos",
            "-Llegar a la meta antes de que acabe el tiempo",
            "-Presiona DFS o BFS para elegir el algoritmo de resolucion",
            "-Activa la IA para resolver el laberinto automaticamente",
            "-Presiona ESPACIO para comenzar"
        ]

        for i, instruction in enumerate(instructions):
            # Dibuja cada instruccion en la pantalla
            self.draw_text(instruction, (self.screen.get_width() // 2 - 150, 200 + i * 40))

        pygame.display.flip()
        waiting = True
        while waiting:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.quit_game()
                if event.type == pygame.KEYDOWN and event.key == pygame.K_SPACE:
                    waiting = False

    def show_win_screen(self):
        # Muestra la pantalla de victoria y pasa al siguiente nivel
        self.show_message_screen("¡Has ganado!", (0, 255, 0))
        self.next_level()

    def show_lose_screen(self, message):
        # Muestra la pantalla de derrota y reinicia el nivel
        self.show_message_screen(message, (255, 0, 0))
        self.reset_level()

    def show_message_screen(self, message, color):
        # Crea una pantalla superpuesta con el mensaje y la puntuacion final
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        message_surf = self.font.render(message, True, color)
        message_rect = message_surf.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
        self.screen.blit(message_surf, message_rect)

        score_surf = self.small_font.render(f"Puntuación final: {self.score}", True, (255, 255, 255))
        score_rect = score_surf.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 + 50))
        self.screen.blit(score_surf, score_rect)

        pygame.display.flip()
        pygame.time.wait(3000)

    def next_level(self):
        # Carga el siguiente nivel o muestra la pantalla de juego completado
        if self.level < 5:
            self.level += 1
            self.start_new_level()
        else:
            self.show_game_complete_screen()

    def start_new_level(self):
        # Carga el mapa del nuevo nivel y muestra las instrucciones
        self.load_map(f"maps/level{self.level}.txt")
        self.ai_solving = False
        self.ai_path = []
        self.start_time = pygame.time.get_ticks()
        self.show_instructions()

    def reset_level(self):
        # Reinicia el nivel actual
        self.__init__(self.level)

    def lose_life(self):
        # Quita una vida al jugador y muestra la pantalla de derrota si se quedan sin vidas
        self.lives -= 1
        self.lose_life_sound.play()
        if self.lives <= 0:
            self.show_lose_screen("¡Te has quedado sin vidas!")
        else:
            self.player.topleft = self.get_safe_position()

    def get_safe_position(self):
        # Encuentra una posicion segura para el jugador
        safe_positions = [rect for rect in self.paths if not any(enemy.colliderect(rect) for enemy in self.enemies)]
        return random.choice(safe_positions).topleft if safe_positions else self.player.topleft

    def show_game_complete_screen(self):
        # Muestra la pantalla de juego completado
        overlay = pygame.Surface((self.screen.get_width(), self.screen.get_height()))
        overlay.set_alpha(200)
        overlay.fill((0, 0, 0))
        self.screen.blit(overlay, (0, 0))

        message_surf = self.font.render("¡Felicidades! Has completado todos los niveles", True, (255, 255, 0))
        message_rect = message_surf.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2))
        self.screen.blit(message_surf, message_rect)

        score_surf = self.small_font.render(f"Puntuación final: {self.score}", True, (255, 255, 255))
        score_rect = score_surf.get_rect(center=(self.screen.get_width() // 2, self.screen.get_height() // 2 + 50))
        self.screen.blit(score_surf, score_rect)

        pygame.display.flip()
        pygame.time.wait(5000)
        self.running = False

    def quit_game(self):
        pygame.quit()
        sys.exit()

if __name__ == "__main__":
    for level in range(1, 6):
        laberinto = Laberinto(level)
        laberinto.run()
        if not laberinto.running:
            break
    pygame.quit()
    sys.exit()