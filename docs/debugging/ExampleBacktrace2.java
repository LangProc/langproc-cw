public class ExampleBacktrace2 {

  /* OOPS: Missing recursive base case */
  public static int fibonaci(int x) {
    return fibonaci(x-1) + fibonaci(x-2);
  }

  public static void main(String[] args)
  {
    System.out.println(fibonaci(10));
  }
}
