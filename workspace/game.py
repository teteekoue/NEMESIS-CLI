#!/usr/bin/env python3
"""
Astarté Game Ludo - Jeu de Ludo simple en ligne de commande
"""

import random
import time
from typing import List, Dict, Optional

class Case:
    """Représente une case du plateau"""
    def __init__(self, numero: int, est_securite: bool = False):
        self.numero = numero
        self.est_securite = est_securite
        self.pions = []  # Liste des pions présents sur cette case

    def peut_recevoir(self, pion: 'Pion') -> bool:
        """Vérifie si un pion peut venir sur cette case"""
        if self.est_securite:
            return True
        if len(self.pions) == 0:
            return True
        # Si un pion adverse est présent, on peut l'éliminer
        return self.pions[0].couleur != pion.couleur

    def arriver(self, pion: 'Pion') -> Optional['Pion']:
        """Fait arriver un pion sur la case, retourne le pion éliminé"""
        pion_elimine = None
        if self.pions and self.pions[0].couleur != pion.couleur and not self.est_securite:
            pion_elimine = self.pions.pop(0)
        self.pions = [pion]
        return pion_elimine

    def partir(self, pion: 'Pion'):
        """Fait partir un pion de la case"""
        if self.pions and self.pions[0] == pion:
            self.pions.pop(0)

class Pion:
    """Représente un pion d'un joueur"""
    def __init__(self, id_pion: int, couleur: str):
        self.id = id_pion
        self.couleur = couleur
        self.position = -1  # -1 = maison, 0 à 51 = cases normales, 52+ = arrivée
        self.est_arrive = False

    def __repr__(self):
        return f"{self.couleur[:2]}{self.id}"

class Joueur:
    """Représente un joueur"""
    def __init__(self, nom: str, couleur: str):
        self.nom = nom
        self.couleur = couleur
        self.pions = [Pion(i, couleur) for i in range(4)]
        self.couleurs_support = {
            'rouge': '31',
            'vert': '32',
            'jaune': '33',
            'bleu': '34'
        }

    def afficher(self, texte: str) -> str:
        """Retourne le texte coloré"""
        code = self.couleurs_support.get(self.couleur, '37')
        return f"\033[{code}m{texte}\033[0m"

class Plateau:
    """Représente le plateau de jeu"""
    def __init__(self):
        self.cases = []
        # Cases de sécurité (cases spéciales)
        cases_securite = [0, 8, 13, 21, 26, 34, 39, 47]
        for i in range(52):
            self.cases.append(Case(i, i in cases_securite))

    def get_position_fin(self, couleur: str, avancee: int) -> int:
        """Calcule la position finale après un déplacement"""
        positions_start = {'rouge': 0, 'vert': 13, 'jaune': 26, 'bleu': 39}
        start = positions_start[couleur]
        return (start + avancee) % 52

class JeuLudo:
    """Classe principale du jeu"""
    def __init__(self):
        self.plateau = Plateau()
        self.joueurs = []
        self.tour = 0
        self.des = None

    def ajouter_joueur(self, nom: str, couleur: str):
        """Ajoute un joueur à la partie"""
        self.joueurs.append(Joueur(nom, couleur))

    def lancer_de(self) -> int:
        """Lance le dé"""
        input("\nAppuyez sur Entrée pour lancer le dé...")
        valeur = random.randint(1, 6)
        print(f"\n🎲 Le dé indique : {valeur} 🎲")
        time.sleep(0.5)
        return valeur

    def pions_sortis(self, joueur: Joueur) -> List[Pion]:
        """Retourne les pions qui sont sortis de la maison"""
        return [p for p in joueur.pions if p.position != -1 and not p.est_arrive]

    def pions_maison(self, joueur: Joueur) -> List[Pion]:
        """Retourne les pions encore dans la maison"""
        return [p for p in joueur.pions if p.position == -1 and not p.est_arrive]

    def pions_arrives(self, joueur: Joueur) -> List[Pion]:
        """Retourne les pions arrivés"""
        return [p for p in joueur.pions if p.est_arrive]

    def afficher_plateau(self):
        """Affiche l'état du plateau"""
        print("\n" + "="*60)
        print("🏆 Astarté Game Ludo 🏆".center(60))
        print("="*60)

        for joueur in self.joueurs:
            pions_sortis = self.pions_sortis(joueur)
            pions_maison = self.pions_maison(joueur)
            pions_arrives = self.pions_arrives(joueur)

            print(f"\n{joueur.afficher(joueur.nom)} ({joueur.couleur})")
            print(f"  🏠 Maison : {[str(p) for p in pions_maison] if pions_maison else 'aucun'}")
            print(f"  🌍 En jeu : {[str(p) for p in pions_sortis] if pions_sortis else 'aucun'}")
            print(f"  🏆 Arrivés : {len(pions_arrives)}/4")

        print("\n" + "-"*60)

    def peut_bouger(self, joueur: Joueur, pion: Pion, deplacement: int) -> bool:
        """Vérifie si un pion peut faire le déplacement demandé"""
        if pion.est_arrive:
            return False

        if pion.position == -1:  # Dans la maison
            return deplacement == 6

        nouvelle_pos = pion.position + deplacement
        if nouvelle_pos > 56:  # Arrivée dépassée
            return False

        if nouvelle_pos == 56:  # Arrivée exacte
            return True

        if nouvelle_pos <= 51:  # Sur le plateau
            case = self.plateau.cases[nouvelle_pos]
            return case.peut_recevoir(pion)

        return False

    def deplacer_pion(self, joueur: Joueur, pion: Pion, deplacement: int) -> bool:
        """Déplace un pion et gère les éliminations"""
        if pion.position == -1:  # Sortie de maison
            pion.position = self.plateau.get_position_fin(joueur.couleur, 0)
            print(f"{joueur.afficher(pion.__repr__())} sort de la maison !")
            return True

        nouvelle_pos = pion.position + deplacement

        if nouvelle_pos > 56:
            print("❌ Déplacement impossible (dépassement de l'arrivée)")
            return False

        if nouvelle_pos == 56:  # Arrivée
            pion.est_arrive = True
            pion.position = 56
            # Retirer le pion de sa case actuelle
            if pion.position - deplacement <= 51:
                ancienne_case = self.plateau.cases[pion.position - deplacement]
                ancienne_case.partir(pion)
            print(f"{joueur.afficher(pion.__repr__())} arrive à destination ! 🏆")
            return True

        if nouvelle_pos <= 51:  # Sur le plateau
            # Retirer de l'ancienne case
            ancienne_case = self.plateau.cases[pion.position]
            ancienne_case.partir(pion)

            # Arriver sur la nouvelle case
            nouvelle_case = self.plateau.cases[nouvelle_pos]
            pion_elimine = nouvelle_case.arriver(pion)

            if pion_elimine:
                pion_elimine.position = -1  # Retour à la maison
                print(f"{joueur.afficher(pion.__repr__())} élimine {pion_elimine.couleur[:2]}{pion_elimine.id} ! 💥")

            pion.position = nouvelle_pos
            return True

        return False

    def jouer_tour(self, joueur: Joueur):
        """Joue un tour pour un joueur"""
        print(f"\n{'='*60}")
        print(f"C'est au tour de {joueur.afficher(joueur.nom)} !")
        print(f"{'='*60}")

        # Vérifier si le joueur a déjà gagné
        if len(self.pions_arrives(joueur)) == 4:
            return

        # Lancer le dé
        de = self.lancer_de()

        # Récupérer les pions disponibles
        pions_deplaçables = []
        for pion in joueur.pions:
            if self.peut_bouger(joueur, pion, de):
                pions_deplaçables.append(pion)

        if not pions_deplaçables:
            print(f"\n❌ Aucun pion ne peut bouger (dé: {de})")
            if de == 6:
                print("🎲 Vous avez fait 6 mais vous ne pouvez pas sortir de pion ou avancer !")
            return

        # Afficher les choix
        print(f"\nPions disponibles (dé: {de}):")
        print("0 - Passer le tour")
        for i, pion in enumerate(pions_deplaçables, 1):
            if pion.position == -1:
                print(f"  {i} - {joueur.afficher(str(pion))} (dans la maison) -> sortie possible !")
            else:
                print(f"  {i} - {joueur.afficher(str(pion))} (position {pion.position})")

        # Choix du joueur
        while True:
            try:
                choix = int(input("\nChoisissez un pion (0 pour passer) : "))
                if choix == 0:
                    print("Tour passé.")
                    return
                if 1 <= choix <= len(pions_deplaçables):
                    pion_choisi = pions_deplaçables[choix - 1]
                    if self.deplacer_pion(joueur, pion_choisi, de):
                        print(f"✅ Pion {joueur.afficher(str(pion_choisi))} déplacé de {de} cases !")
                        if de == 6:
                            print("🎲 Vous avez fait 6 ! Vous rejouez ! 🎲")
                            self.jouer_tour(joueur)
                        return
                    else:
                        print("❌ Déplacement impossible")
                else:
                    print("Choix invalide")
            except ValueError:
                print("Entrez un nombre valide")

    def demarrer(self):
        """Démarre la partie"""
        print("\n" + "🏆 BIENVENUE DANS Astarté Game Ludo 🏆".center(60))
        print("\nRègles :")
        print("- Chaque joueur a 4 pions")
        print("- Faites 6 pour sortir un pion de la maison")
        print("- Le premier à amener ses 4 pions à l'arrivée gagne")
        print("- Les cases de sécurité protègent vos pions")
        print("- Vous pouvez éliminer les pions adverses en atterrissant sur leur case")
        print("- Faire 6 donne un tour supplémentaire")

        # Configuration des joueurs
        nb_joueurs = 0
        while nb_joueurs < 2 or nb_joueurs > 4:
            try:
                nb_joueurs = int(input("\nNombre de joueurs (2-4) : "))
                if nb_joueurs < 2 or nb_joueurs > 4:
                    print("Veuillez entrer 2, 3 ou 4 joueurs")
            except ValueError:
                print("Entrez un nombre valide")

        couleurs = ['rouge', 'vert', 'jaune', 'bleu']
        for i in range(nb_joueurs):
            nom = input(f"Nom du joueur {i+1} (couleur {couleurs[i]}) : ")
            if not nom.strip():
                nom = f"Joueur {i+1}"
            self.ajouter_joueur(nom.strip(), couleurs[i])

        # Boucle principale du jeu
        game_over = False
        while not game_over:
            joueur_actuel = self.joueurs[self.tour]

            # Vérifier si le joueur actuel a gagné
            if len(self.pions_arrives(joueur_actuel)) == 4:
                print(f"\n{'='*60}")
                print(f"🏆 {joueur_actuel.afficher(joueur_actuel.nom)} A GAGNÉ LA PARTIE ! 🏆")
                print(f"{'='*60}")
                game_over = True
                break

            self.afficher_plateau()
            self.jouer_tour(joueur_actuel)
            self.tour = (self.tour + 1) % len(self.joueurs)

        print("\nMerci d'avoir joué à Astarté Game Ludo !")

def main():
    jeu = JeuLudo()
    jeu.demarrer()

if __name__ == "__main__":
    main()
