package org.javaup.commerce;

public class CommerceProblem extends RuntimeException {
  public final int status;

  public CommerceProblem(int status, String message) {
    super(message);
    this.status = status;
  }

  public static void require(boolean condition, int status, String message) {
    if (!condition) throw new CommerceProblem(status, message);
  }
}
