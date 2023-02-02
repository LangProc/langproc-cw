#include <stdio.h>
#include <stdlib.h>

struct tree_t {
  int val;
  struct tree_t *left;
  struct tree_t *right;
};

typedef struct tree_t* treeptr;

static treeptr build_binary_tree
()
{
  treeptr n0 = (treeptr) malloc(sizeof(struct tree_t));
  treeptr n1 = (treeptr) malloc(sizeof(struct tree_t));
  treeptr n2 = (treeptr) malloc(sizeof(struct tree_t));
  treeptr n3 = (treeptr) malloc(sizeof(struct tree_t));
  treeptr n4 = (treeptr) malloc(sizeof(struct tree_t));
  treeptr n5 = (treeptr) malloc(sizeof(int));  // TODO: THIS IS A BUG

  n0->left = n1;
  n0->right = n2;
  n0->val = 10;

  n1->left = n3;
  n1->right = n4;
  n1->val = 5;

  n2->left = n5;
  n2->right = NULL;
  n2->val = 7;

  n3->left = NULL;
  n3->right = NULL;
  n3->val = 6;

  n4->left = NULL;
  n4->right = NULL;
  n4->val = 8;

  n5->val = 9;
  // TODO: MISSING n5->left and n5->right assignment

  return n0;
}

static void inorder_print(int indent, treeptr tree)
{
  if (tree == NULL) {
    return;
  }

  inorder_print(indent + 1, tree->left);
  for (int i = 0 ; i < indent * 4; i++) {
    printf(" ");
  }
  printf("%d\n", tree->val);
  inorder_print(indent + 1, tree->right);
}


int main
(int argc, char * argv[])
{
  treeptr tree = build_binary_tree();
  inorder_print(0, tree);
}
